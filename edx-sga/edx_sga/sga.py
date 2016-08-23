"""
This block defines a Staff Graded Assignment.  Students are shown a rubric
and invited to upload a file which is then graded by staff.
"""
import datetime
import hashlib
import json
import logging
import mimetypes
import os
import pkg_resources
import pytz
import requests
import shutil
import time
import re

from tempfile import mkdtemp
from functools import partial

from courseware.models import StudentModule

from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.conf import settings
from django.template import Context, Template
from django.contrib.auth.models import User
from django.utils._os import safe_join

from student.models import anonymous_id_for_user, user_by_anonymous_id
from submissions import api as submissions_api
from submissions.models import StudentItem as SubmissionsStudent

from webob.response import Response

from xblock.core import XBlock
from xblock.exceptions import JsonHandlerError
from xblock.fields import DateTime, Scope, String, Float, Integer, Dict, Boolean
from xblock.fragment import Fragment

from xmodule.util.duedate import get_extended_due_date


log = logging.getLogger(__name__)
BLOCK_SIZE = 8 * 1024
assignments_zip_file_name = 'assignments.zip'


def reify(meth):
    """
    Decorator which caches value so it is only computed once.
    Keyword arguments:
    inst
    """
    def getter(inst):
        """
        Set value to meth name in dict and returns value.
        """
        value = meth(inst)
        inst.__dict__[meth.__name__] = value
        return value
    return property(getter)


class StaffGradedAssignmentXBlock(XBlock):
    """
    This block defines a Staff Graded Assignment.  Students are shown a rubric
    and invited to upload a file which is then graded by staff.
    """
    has_score = True
    icon_class = 'problem'
    STUDENT_FILEUPLOAD_MAX_SIZE = 4 * 1000 * 1000  # 4 MB
    dummy_submission_answer = 'dummy submission for group assignment'

    display_name = String(
        default='Staff Graded Assignment', scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of "
             "the page."
    )

    weight = Float(
        display_name="Problem Weight",
        help=("Defines the number of points each problem is worth. "
              "If the value is not set, the problem is worth the sum of the "
              "option point values."),
        values={"min": 0, "step": .1},
        scope=Scope.settings
    )

    points = Integer(
        display_name="Maximum score",
        help=("Maximum grade score given to assignment by staff."),
        default=100,
        scope=Scope.settings
    )

    staff_score = Integer(
        display_name="Score assigned by non-instructor staff",
        help=("Score will need to be approved by instructor before being "
              "published."),
        default=None,
        scope=Scope.settings
    )

    enable_upload = Boolean(
        display_name="Enable file uploads",
        help=("Allow Students to upload files."),
        default=True,
        scope=Scope.settings
    )

    show_all_submissions = Boolean(
        display_name="Show all submissions",
        help=("Show all student submissions."),
        default=False,
        scope=Scope.settings
    )

    email_subject = String(
        display_name="Email subject",
        help=("Student feedback email subject."),
        default='Your feedback is ready',
        scope=Scope.settings
    )

    email_body = String(
        display_name="Email Body",
        help=("Student feedback email body."),
        default='Hello,\n\nYour assignment feedback is ready.\n\nKind regards,\n\nThe IMD Learning Team',
        scope=Scope.settings
    )

    users_excluded_email = String(
        scope=Scope.settings,
        display_name="Users to exclude by email",
        default='',
        help="A list of email addresses of users that should not be shown. Wildcards are allowed, e.g. *.imd.org"
    )

    comment = String(
        display_name="Instructor comment",
        default='',
        scope=Scope.user_state,
        help="Feedback given to student by instructor."
    )

    annotated_sha1 = String(
        display_name="Annotated SHA1",
        scope=Scope.user_state,
        default=None,
        help=("sha1 of the annotated file uploaded by the instructor for "
              "this assignment.")
    )

    annotated_filename = String(
        display_name="Annotated file name",
        scope=Scope.user_state,
        default=None,
        help="The name of the annotated file uploaded for this assignment."
    )

    annotated_mimetype = String(
        display_name="Mime type of annotated file",
        scope=Scope.user_state,
        default=None,
        help="The mimetype of the annotated file uploaded for this assignment."
    )

    annotated_timestamp = DateTime(
        display_name="Timestamp",
        scope=Scope.user_state,
        default=None,
        help="When the annotated file was uploaded"
    )

    feedback_video = Dict(
        display_name="Video Feedback",
        scope=Scope.user_state,
        default=None,
        help="Video feedback from the Instructor"
    )

    def max_score(self):
        """
        Return the maximum score possible.
        """
        return self.points

    @reify
    def block_id(self):
        """
        Return the usage_id of the block.
        """
        return self.scope_ids.usage_id

    def get_logged_in_student_id(self):
        student_id = self.xmodule_runtime.anonymous_student_id
        assert student_id != (
            'MOCK', "Forgot to call 'personalize' in test."
        )
        return student_id

    def student_item_dict(self, student_id=None):
        # pylint: disable=no-member
        """
        Returns dict required by the submissions app for creating and
        retrieving submissions for a particular student.
        """
        return {
            "student_id": student_id or self.get_logged_in_student_id(),
            "course_id": self.course_id,
            "item_id": self.block_id,
            "item_type": 'sga'
        }

    def create_submission(self, student_id=None, answer=None):
        # pylint: disable=no-member
        """
        Creates a submission for a particular student. If no answer passed then
        create a dummy submission with a dummy answer (to be used for grading
        group assignments).
        """
        if (answer is None):
            answer = self.dummy_submission_answer
        return submissions_api.create_submission(self.student_item_dict(student_id), answer)

    def student_submission_id(self, submission_id=None):
        # pylint: disable=no-member
        """
        Returns dict required by the submissions app for creating and
        retrieving submissions for a particular student.
        """
        if submission_id is None:
            submission_id = self.xmodule_runtime.anonymous_student_id
            assert submission_id != (
                'MOCK', "Forgot to call 'personalize' in test."
            )
        return {
            "student_id": submission_id,
            "course_id": self.course_id,
            "item_id": self.block_id,
            "item_type": 'sga',  # ???
        }

    def get_submission(self, submission_id=None):
        """
        Get student's most recent submission.
        """
        submissions = submissions_api.get_submissions(
            self.student_submission_id(submission_id))
        if submissions:
            # If I understand docs correctly, most recent submission should
            # be first
            return submissions[0]

    '''def get_submission(self, student_id=None):
        """
        Get student's most recent submission.
        """
        submissions = submissions_api.get_submissions(self.student_item_dict(student_id))
        if submissions:
            # If I understand docs correctly, most recent submission should
            # be first
            return submissions[0]'''

    def get_score(self, submission_id=None):
        """
        Return student's current score.
        """
        score = submissions_api.get_score(self.student_submission_id(submission_id))
        if score:
            return score['points_earned']

    @reify
    def score(self):
        """
        Return score from submissions.
        """
        return self.get_score()

    def student_view(self, context=None):
        # pylint: disable=no-member
        """
        The primary view of the StaffGradedAssignmentXBlock, shown to students
        when viewing courses.
        """
        context = {
            "student_state": json.dumps(self.student_state()),
            "id": self.location.name.replace('.', '_'),
            "max_file_size": getattr(
                settings, "STUDENT_FILEUPLOAD_MAX_SIZE",
                self.STUDENT_FILEUPLOAD_MAX_SIZE
            )
        }
        if self.show_staff_grading_interface():
            context['is_course_staff'] = True
            self.update_staff_debug_context(context)

        fragment = Fragment()
        fragment.add_content(
            render_template(
                'templates/staff_graded_assignment/show.html',
                context
            )
        )
        fragment.add_css(_resource("static/css/edx_sga.css"))

        fragment.add_javascript(_resource("static/js/src/jquery.tablesorter.min.js"))
        fragment.add_javascript(_resource("static/js/src/imd.leanmodal.js"))

        # videojs
        fragment.add_css_url("https://vjs.zencdn.net/5.8.0/video-js.css")
        fragment.add_javascript_url("https://vjs.zencdn.net/ie8/1.1.2/videojs-ie8.min.js")
        fragment.add_javascript_url("https://vjs.zencdn.net/5.8.0/video.js")

        fragment.add_javascript(_resource("static/js/src/imd.videorecorder.js"))
        fragment.add_javascript(_resource("static/js/src/edx_sga.js"))

        fragment.initialize_js('StaffGradedAssignmentXBlock')
        return fragment

    def update_staff_debug_context(self, context):
        # pylint: disable=no-member
        """
        Add context info for the Staff Debug interface.
        """
        published = self.start
        context['is_released'] = published and published < _now()
        context['location'] = self.location
        context['category'] = type(self).__name__
        context['fields'] = [
            (name, field.read_from(self))
            for name, field in self.fields.items()]

    def renderable_comment(self, comment):
        if (len(comment) > 0):
            return Template('{{ comment|urlize|linebreaks }}').render(Context({"comment": comment}))
        else:
            return ''

    def student_state(self):
        """
        Returns a JSON serializable representation of student's state for
        rendering in client view.
        """
        submission = self.get_submission()
        uploaded = None
        if submission and 'filename' in submission['answer']:
            uploaded = {"filename": submission['answer']['filename']}

        if self.annotated_sha1:
            annotated = {"filename": self.annotated_filename}
        else:
            annotated = None

        score = self.score
        if score is not None:
            comment_html = self.renderable_comment(self.comment)
            graded = {'score': score, 'comment': comment_html}
        else:
            graded = None

        all_student_submissions = None
        if self.show_all_submissions:
            all_student_submissions = self.get_all_student_submissions()

        self.updateFeedbackVideoUrls()

        return {
            "display_name": self.display_name,
            "enable_upload": self.enable_upload,
            "all_student_submissions": all_student_submissions,
            "uploaded": uploaded,
            "annotated": annotated,
            "graded": graded,
            "max_score": self.max_score(),
            "upload_allowed": self.upload_allowed(),
            "feedback_video": self.feedback_video,
            "course_is_cohorted": self.is_course_cohorted(self.course_id)
        }

    def get_all_student_submissions(self):
        submissions = []
        users = self.all_students_for_course()
        for user in users:
            student_id = anonymous_id_for_user(user, self.course_id)
            submission = self.get_submission(student_id)
            if submission:
                if 'filename' in submission['answer']:
                    filename = submission['answer']['filename']
                    submission_date_formatted = formatDateTime(submission['created_at'])
                    submissions.append({
                        'student_id': student_id,
                        'username': user.username,
                        'filename': filename,
                        'submission_date': submission_date_formatted
                    })
        submissions.sort(key=lambda sub: sub['username'].lower())
        return submissions

    def all_students_for_course(self):
        students = User.objects.filter(
            is_active=True,
            courseenrollment__course_id=self.course_id,
            courseenrollment__is_active=True
        )
        return students

    def regexp_from_users_excluded_email(self, users_excluded_email):
        regexp_string = ''
        emails = users_excluded_email.split('\n')
        for email in emails:
            if len(email) > 0:
                regexp = '^' + email + '$'
                regexp = regexp.replace('.', '\\.')
                regexp = regexp.replace('*', '.*')
                if len(regexp_string) > 0:
                    regexp_string += '|' + regexp
                else:
                    regexp_string += regexp
        log.info('regexp: %s', regexp_string)
        return regexp_string

    def staff_grading_data(self):
        """
        Return student assignment information for display on the
        grading screen.
        """
        def get_student_data():
            # pylint: disable=no-member
            """
            Returns a dict of student assignment information along with
            annotated file name, student id and module id, this
            information will be used on grading screen
            """
            # Submissions doesn't have API for this, just use model directly.
            students = SubmissionsStudent.objects.filter(
                course_id=self.course_id,
                item_id=self.block_id)
            for student in students:
                submission = self.get_submission(student.student_id)
                if not submission:
                    continue
                user = user_by_anonymous_id(student.student_id)
                module, created = StudentModule.objects.get_or_create(
                    course_id=self.course_id,
                    module_state_key=self.location,
                    student=user,
                    defaults={
                        'state': '{}',
                        'module_type': self.category,
                    })
                if created:
                    log.info(
                        "Init for course:%s module:%s student:%s  ",
                        module.course_id,
                        module.module_state_key,
                        module.student.username
                    )

                state = json.loads(module.state)
                score = self.get_score(student.student_id)
                approved = score is not None
                if score is None:
                    score = state.get('staff_score')
                    needs_approval = score is not None
                else:
                    needs_approval = False
                instructor = self.is_instructor()
                yield {
                    'module_id': module.id,
                    'student_id': student.student_id,
                    'submission_id': submission['uuid'],
                    'username': module.student.username,
                    'fullname': module.student.profile.name,
                    'filename': submission['answer']["filename"],
                    'timestamp': submission['created_at'].strftime(
                        DateTime.DATETIME_FORMAT
                    ),
                    'score': score,
                    'approved': approved,
                    'needs_approval': instructor and needs_approval,
                    'may_grade': instructor or not approved,
                    'annotated': state.get("annotated_filename"),
                    'comment': state.get("comment", ''),
                }

        return {
            'assignments': list(get_student_data()),
            'max_score': self.max_score(),
            'display_name': self.display_name
        }

    def students_for_course(self, regexp=None):
        students = User.objects.filter(
            is_active=True,
            courseenrollment__course_id=self.course_id,
            courseenrollment__is_active=True,
        )
        if regexp and len(regexp) > 0:
            students = students.exclude(
                email__iregex=regexp,
            )
        return students

    def studio_view(self, context=None):
        """
        Return fragment for editing block in studio.
        """
        try:
            cls = type(self)

            def none_to_empty(data):
                """
                Return empty string if data is None else return data.
                """
                return data if data is not None else ''
            edit_fields = (
                (field, type, none_to_empty(getattr(self, field.name)), validator)
                for field, type, validator in (
                    (cls.display_name, 'String', 'string'),
                    (cls.points, 'Integer', 'number'),
                    (cls.weight, 'Float', 'number'),
                    (cls.enable_upload, 'Boolean', 'number'),
                    (cls.show_all_submissions, 'Boolean', 'number'),
                    (cls.email_subject, 'String', 'string'),
                    (cls.email_body, 'TextArea', 'string'),
                    (cls.users_excluded_email, 'TextArea', 'string'),
                )
            )

            context = {
                'fields': edit_fields
            }
            fragment = Fragment()
            fragment.add_content(
                render_template(
                    'templates/staff_graded_assignment/edit.html',
                    context
                )
            )
            fragment.add_javascript(_resource("static/js/src/studio.js"))
            fragment.initialize_js('StaffGradedAssignmentXBlock')
            return fragment
        except:  # pragma: NO COVER
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

    @XBlock.json_handler
    def save_sga(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Persist block data when updating settings in studio.
        """
        self.display_name = data.get('display_name', self.display_name)

        # Validate points before saving
        points = data.get('points', self.points)
        # Check that we are an int
        try:
            points = int(points)
        except ValueError:
            raise JsonHandlerError(400, 'Points must be an integer')
        # Check that we are positive
        if points < 0:
            raise JsonHandlerError(400, 'Points must be a positive integer')
        self.points = points

        # Validate weight before saving
        weight = data.get('weight', self.weight)
        # Check that weight is a float.
        if weight:
            try:
                weight = float(weight)
            except ValueError:
                raise JsonHandlerError(400, 'Weight must be a decimal number')
            # Check that we are positive
            if weight < 0:
                raise JsonHandlerError(
                    400, 'Weight must be a positive decimal number'
                )
        self.weight = weight
        self.enable_upload = True if data['enable_upload'] == "True" else False
        self.show_all_submissions = True if data['show_all_submissions'] == "True" else False
        self.email_subject = data.get('email_subject', self.email_subject)
        self.email_body = data.get('email_body', self.email_body)

        users_excluded_email = data.get('users_excluded_email', self.users_excluded_email)
        try:
            regexp_string = self.regexp_from_users_excluded_email(users_excluded_email)
            re.compile(regexp_string)
        except:
            raise JsonHandlerError(400, 'Users to exclude by email is causing an error, please edit.')
        self.users_excluded_email = users_excluded_email

    @XBlock.handler
    def upload_assignment(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Save a students submission file.
        """
        require(self.upload_allowed())
        upload = request.params['assignment']
        sha1 = _get_sha1(upload.file)
        answer = {
            "sha1": sha1,
            "filename": upload.file.name,
            "mimetype": mimetypes.guess_type(upload.file.name)[0],
        }
        self.create_submission(answer=answer)
        path = self._file_storage_path(sha1, upload.file.name)
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        return Response(json_body=self.student_state())

    @XBlock.json_handler
    def remove_assignment(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Removes a students submission.
        """
        require(self.upload_allowed())
        self.create_submission(answer='')
        return Response(json_body=self.student_state())

    @XBlock.handler
    def staff_upload_annotated(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Save annotated assignment from staff.
        """
        require(self.is_course_staff())
        upload = request.params['annotated']
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['annotated_sha1'] = sha1 = _get_sha1(upload.file)
        state['annotated_filename'] = filename = upload.file.name
        state['annotated_mimetype'] = mimetypes.guess_type(upload.file.name)[0]
        state['annotated_timestamp'] = _now().strftime(
            DateTime.DATETIME_FORMAT
        )
        path = self._file_storage_path(sha1, filename)
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        module.state = json.dumps(state)
        module.save()
        log.info(
            "staff_upload_annotated for course:%s module:%s student:%s ",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def download_assignment(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Fetch student assignment from storage and return it.
        """
        answer = self.get_submission()['answer']
        path = self._file_storage_path(answer['sha1'], answer['filename'])
        return self.download(path, answer['mimetype'], answer['filename'])

    @XBlock.handler
    def download_annotated(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Fetch assignment with staff annotations from storage and return it.
        """
        path = self._file_storage_path(
            self.annotated_sha1,
            self.annotated_filename,
        )
        return self.download(
            path,
            self.annotated_mimetype,
            self.annotated_filename
        )

    @XBlock.handler
    def staff_download(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return an assignment file requested by staff.
        """
        require(self.is_course_staff())
        submission = self.get_submission(request.params['student_id'])
        answer = submission['answer']
        path = self._file_storage_path(answer['sha1'], answer['filename'])
        return self.download(
            path,
            answer['mimetype'],
            answer['filename'],
            require_staff=True
        )

    @XBlock.handler
    def download_student_assignment(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Fetch a particular student assignment from storage and return it.
        """
        submission = self.get_submission(request.params['student_id'])
        answer = submission['answer']
        path = self._file_storage_path(answer['sha1'], answer['filename'])
        return self.download(
            path,
            answer['mimetype'],
            answer['filename']
        )

    @XBlock.json_handler
    def staff_create_download_assignments_zip(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Return a set of assignments in a zip file requested by staff.
        """
        require(self.is_course_staff())
        student_ids = data['student_ids']
        log.info("staff_create_download_assignments_zip for student_ids: %s", student_ids)

        temp_dir = mkdtemp(dir=settings.DATA_DIR)
        zipfile_path = self.zipAssignments(student_ids, temp_dir, assignments_zip_file_name)
        log.info('created assignments zipfile: %s', zipfile_path)
        return {
            'id': os.path.basename(temp_dir),
        }

    @XBlock.handler
    def staff_download_assignments(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return a set of assignments in a zip file requested by staff.
        """
        require(self.is_course_staff())

        tmp_dirname = request.params['id']
        if tmp_dirname.startswith('tmp'):
            temp_dir = safe_join(settings.DATA_DIR, tmp_dirname)
            zipfile_path = safe_join(temp_dir, assignments_zip_file_name)
            log.info('downloading assignments zipfile: %s', zipfile_path)

            try:
                zipf = File(open(zipfile_path, 'rb'))
                app_iter = iter(partial(zipf.read, BLOCK_SIZE), '')
                return Response(
                    app_iter=app_iter,
                    content_type='application/zip',
                    content_disposition="attachment; filename=\"" + assignments_zip_file_name + "\"")
            except Exception as e:
                log.info("staff_download_assignments error: %s", e)
                return Response(
                    "Sorry, we could not download the requested student assignments. Please contact {}".format(
                        settings.TECH_SUPPORT_EMAIL
                    ),
                    status_code=500
                )
            finally:
                shutil.rmtree(temp_dir)

    def zipAssignments(self, student_ids, temp_dir, zip_file_name):
        assignments_dirname = "{}_{}".format(self.location.course, self.display_name.replace(' ', '_'))
        assignments_dirpath = safe_join(temp_dir, assignments_dirname)
        os.mkdir(assignments_dirpath)
        self.copyAssignmentsToDir(student_ids, assignments_dirpath)

        zip_file_name_no_ext = os.path.splitext(os.path.basename(zip_file_name))[0]
        current_dir = os.getcwd()
        os.chdir(temp_dir)
        shutil.make_archive(zip_file_name_no_ext, 'zip', temp_dir, assignments_dirname)
        os.chdir(current_dir)

        return safe_join(temp_dir, zip_file_name)

    def copyAssignmentsToDir(self, student_ids, dir):

        def assignment_file_name(submission, user, filename):
            submission_date_formatted = submission['created_at'].strftime('%b_%d_%Y_%H_%M')
            file_ext = os.path.splitext(filename)[1]
            assignment_filename = self.location.course + '_' + self.display_name.replace(' ', '_') + '_' + user.profile.name.replace(' ', '_') + '_' + submission_date_formatted + file_ext
            return assignment_filename

        for student_id in student_ids:
            submission = self.get_submission(student_id)
            try:
                answer = submission['answer']
                if 'filename' in answer:
                    filename = answer['filename']
                    path = self._file_storage_path(answer['sha1'], filename)
                    src_path = default_storage.path(path)
                    user = user_by_anonymous_id(student_id)
                    dst_path = safe_join(dir, assignment_file_name(submission, user, filename))
                    shutil.copy(src_path, dst_path)
            except Exception as e:
                log.warn("Could not copy assignment: %s", e)

    @XBlock.handler
    def staff_download_annotated(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return annotated assignment file requested by staff.
        """
        require(self.is_course_staff())
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        path = self._file_storage_path(
            state['annotated_sha1'],
            state['annotated_filename']
        )
        return self.download(
            path,
            state['annotated_mimetype'],
            state['annotated_filename'],
            require_staff=True
        )

    def download(self, path, mime_type, filename, require_staff=False):
        """
        Return a file from storage and return in a Response.
        """
        try:
            file_descriptor = default_storage.open(path)
            app_iter = iter(partial(file_descriptor.read, BLOCK_SIZE), '')
            return Response(
                app_iter=app_iter,
                content_type=mime_type,
                content_disposition="attachment; filename=\"" + filename.encode('utf-8') + "\"")
        except IOError:
            if require_staff:
                return Response(
                    "Sorry, assignment {} cannot be found at"
                    " {}. Please contact {}".format(
                        filename.encode('utf-8'), path, settings.TECH_SUPPORT_EMAIL
                    ),
                    status_code=404
                )
            return Response(
                "Sorry, the file you uploaded, {}, cannot be"
                " found. Please try uploading it again or contact"
                " course staff".format(filename.encode('utf-8')),
                status_code=404
            )

    @XBlock.handler
    def get_staff_grading_data(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return the html for the staff grading view
        """
        require(self.is_course_staff())
        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def enter_grade(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Persist a score for a student given by staff.
        """
        require(self.is_course_staff())
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        score = int(request.params['grade'])
        uuid = request.params['submission_id']
        if not uuid:
            # create a dummy submission for student for group assignment
            student_id = request.params['student_id']
            submission = self.create_submission(student_id=student_id)
            uuid = submission['uuid']

        if self.is_instructor():
            submissions_api.set_score(uuid, score, self.max_score())
        else:
            state['staff_score'] = score
        state['comment'] = request.params.get('comment', '')
        module.state = json.dumps(state)
        module.save()
        log.info(
            "enter_grade for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username
        )

        return Response(json_body=self.staff_grading_data())

    @XBlock.handler
    def remove_grade(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Reset a students score request by staff.
        """
        require(self.is_course_staff())
        student_id = request.params['student_id']
        submissions_api.reset_score(student_id, self.course_id, self.block_id)
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['staff_score'] = None
        state['comment'] = ''
        state['annotated_sha1'] = None
        state['annotated_filename'] = None
        state['annotated_mimetype'] = None
        state['annotated_timestamp'] = None
        module.state = json.dumps(state)
        module.save()
        log.info(
            "remove_grade for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.staff_grading_data())

    @XBlock.json_handler
    def add_feedback_video(self, data, suffix=''):
        """
        Save video feedback from staff.
        """
        require(self.is_course_staff())

        kulu_id = data['kulu_id']
        if (kulu_id):
            template_kulu_valley_preview_url = "https://imd.kuluvalley.com/kulu/{}/thumbnail?v=18"
            thumbnail_url = template_kulu_valley_preview_url.format(kulu_id)

            try:
                mp4_url, hls_url = self.get_video_urls(kulu_id) # may not be available at this point

                module = StudentModule.objects.get(pk=data['module_id'])
                state = json.loads(module.state)
                state['feedback_video'] = {
                    'kulu_id': kulu_id,
                    'mp4_url': mp4_url,
                    'hls_url': hls_url,
                    'thumbnail_url': thumbnail_url,
                    'added_by': self.logged_in_username(),
                    'added_on': _now().strftime(DateTime.DATETIME_FORMAT)
                }
                module.state = json.dumps(state)
                module.save()
                log.info(
                    "add_feedback_video for course:%s module:%s student:%s",
                    module.course_id,
                    module.module_state_key,
                    module.student.username
                )

            except requests.exceptions.HTTPError as e:
                if (e.response.status_code == 404):
                    raise JsonHandlerError(404, 'video not found')
                else:
                    raise JsonHandlerError(500, 'an error occurred')
            except:
                raise JsonHandlerError(500, 'an error occurred')

            return Response(json_body=self.staff_grading_data())

    @XBlock.json_handler
    def fetch_feedback_video_urls(self, data, suffix=''):
        """
        Updates the feedback video urls for a student, and returns them.
        """
        require(self.is_course_staff())

        module = StudentModule.objects.get(pk=data['module_id'])
        state = json.loads(module.state)

        if (state['feedback_video']):
            kulu_id = state['feedback_video']['kulu_id']

            try:
                mp4_url, hls_url = self.get_video_urls(kulu_id)

                if (mp4_url or hls_url):
                    state['feedback_video']['mp4_url'] = mp4_url
                    state['feedback_video']['hls_url'] = hls_url
                    module.state = json.dumps(state)
                    module.save()

                log.info(
                    "fetch_feedback_video_urls for course:%s module:%s student:%s",
                    module.course_id,
                    module.module_state_key,
                    module.student.username
                )
                return {
                    'mp4_url': mp4_url,
                    'hls_url': hls_url
                }
            except requests.exceptions.HTTPError as e:
                if (e.response.status_code == 404):
                    raise JsonHandlerError(404, 'video not found')
                else:
                    raise JsonHandlerError(500, 'an error occurred')
            except:
                raise JsonHandlerError(500, 'an error occurred')

    @XBlock.json_handler
    def remove_feedback_video(self, data, suffix=''):
        """
        Remove video feedback from staff.
        """
        require(self.is_course_staff())
        module = StudentModule.objects.get(pk=data['module_id'])
        state = json.loads(module.state)
        state['feedback_video'] = None
        module.state = json.dumps(state)
        module.save()
        log.info(
            "remove_feedback_video for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.staff_grading_data())

    def updateFeedbackVideoUrls(self):
        feedback_video = self.feedback_video
        if (feedback_video and
                (feedback_video['mp4_url'] is None or feedback_video['hls_url'] is None)):

            log.warning("student feedback video is missing urls: kulu_id=%s mp4_url=%s, hls_url=%s",
                        feedback_video['kulu_id'], feedback_video['mp4_url'], feedback_video['hls_url'])
            log.info(
                "updating student feedback video for course:%s module:%s student:%s",
                self.course_id,
                self.location,
                self.logged_in_username()
            )
            try:
                mp4_url, hls_url = self.get_video_urls(feedback_video['kulu_id'])
                feedback_video['mp4_url'] = mp4_url
                feedback_video['hls_url'] = hls_url
                self.feedback_video = feedback_video
            except Exception as e:
                log.info("An error occurred in updateFeedbackVideoUrls: %s", e.message)

    def get_video_urls(self, kulu_id):
        """
        Call KV api to get mp4/hls urls.
        """
        mp4_url = None
        hls_url = None
        if (kulu_id):
            def fetch_kulu_urls(kulu_id):
                mp4_url = None
                hls_url = None
                kulu_valley_kulus_url = "https://imd.kuluvalley.com/api/2.1/rest/kulus/"
                r = requests.get(kulu_valley_kulus_url + kulu_id)
                if (r.status_code == requests.codes.ok):
                    o = r.json()
                    variants = o["kulu"]["media"]["variants"]
                    for variant in variants:
                        if (variant["formatCode"] == "hls_default"):
                            hls_url = variant["url"]
                        if (variant["formatCode"] == "mobile_mp4"):
                            mp4_url = variant["url"]

                    log.info("hls_url = %s", hls_url)
                    log.info("mp4_url = %s", mp4_url)
                r.raise_for_status()
                return mp4_url, hls_url

            retry = 1
            max_retries = 1

            log.info("getting kulu valley urls")
            mp4_url, hls_url = fetch_kulu_urls(kulu_id)

            while (retry <= max_retries and (mp4_url is None or hls_url is None)):
                log.info("getting kulu valley urls: retry %d", retry)
                sleep_for = 2 ** (retry-1) # 1, 2, 4.. seconds
                log.info("sleeping for %.1f seconds", sleep_for)
                time.sleep(sleep_for)
                mp4_url, hls_url = fetch_kulu_urls(kulu_id)
                retry += 1

        return mp4_url, hls_url

    def logged_in_username(self):
        loggedInUser = User.objects.get(id=self.scope_ids.user_id)
        return loggedInUser.username

    def is_course_staff(self):
        # pylint: disable=no-member
        """
         Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    def is_instructor(self):
        # pylint: disable=no-member
        """
        Check if user role is instructor.
        """
        return self.xmodule_runtime.get_user_role() == 'instructor'

    def show_staff_grading_interface(self):
        """
        Return if current user is staff and not in studio.
        """
        in_studio_preview = self.scope_ids.user_id is None
        return self.is_course_staff() and not in_studio_preview

    def past_due(self):
        """
        Return whether due date has passed.
        """
        due = get_extended_due_date(self)
        if due is not None:
            return _now() > due
        return False

    def upload_allowed(self):
        """
        Return whether student is allowed to submit an assignment.
        """
        return self.enable_upload and not self.past_due() and self.score is None

    def _file_storage_path(self, sha1, filename):
        # pylint: disable=no-member
        """
        Get file path of storage.
        """
        path = (
            '{loc.org}/{loc.course}/{loc.block_type}/{loc.block_id}'
            '/{sha1}{ext}'.format(
                loc=self.location,
                sha1=sha1,
                ext=os.path.splitext(filename)[1]
            )
        )
        return path

    def is_course_cohorted(self, course_id):
        try:
            from openedx.core.djangoapps.course_groups.cohorts import is_course_cohorted
            return is_course_cohorted(course_id)
        except Exception as e:
            log.info("error getting cohort function: %s", e.message)
            return False

    def get_cohort(self, user, course_id):
        try:
            from openedx.core.djangoapps.course_groups.cohorts import get_cohort
            return get_cohort(user, course_id)
        except Exception as e:
            log.info("error getting cohort function: %s", e.message)
            return None

def _get_sha1(file_descriptor):
    """
    Get file hex digest (fingerprint).
    """
    sha1 = hashlib.sha1()
    for block in iter(partial(file_descriptor.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file_descriptor.seek(0)
    return sha1.hexdigest()


def _resource(path):  # pragma: NO COVER
    """
    Handy helper for getting resources from our kit.
    """
    data = pkg_resources.resource_string(__name__, path)
    return data.decode("utf8")


def _now():
    """
    Get current date and time.
    """
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


def load_resource(resource_path):  # pragma: NO COVER
    """
    Gets the content of a resource
    """
    resource_content = pkg_resources.resource_string(__name__, resource_path)
    return unicode(resource_content)


def render_template(template_path, context=None):  # pragma: NO COVER
    """
    Evaluate a template by resource path, applying the provided context.
    """
    if context is None:
        context = {}

    template_str = load_resource(template_path)
    template = Template(template_str)
    return template.render(Context(context))


def formatDateTime(dateTime):
    return dateTime.strftime('%b %d %Y %H:%M (UTC)')

def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied
