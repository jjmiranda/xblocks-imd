"""
This XBlock provides feedback to a student via text/html, document and video. It allows staff to manage feedback
for all students on a course.
"""

import logging
import pkg_resources
import json
import datetime
import hashlib
import mimetypes
import pytz
import os
import requests
import time
import re

from functools import partial
from webob.response import Response

log = logging.getLogger(__name__)
BLOCK_SIZE = 8 * 1024

from django.core.exceptions import PermissionDenied
from django.core.files import File
from django.core.files.storage import default_storage
from django.template import Context, Template
from django.contrib.auth.models import User
from django.conf import settings

from xblock.core import XBlock
from xblock.fields import DateTime, Scope, String, Boolean, Dict
from xblock.fragment import Fragment
from xblock.exceptions import JsonHandlerError

from courseware.models import StudentModule

from student.models import anonymous_id_for_user


class FeedbackXBlock(XBlock):
    """
    This XBlock shows student feedback and a staff view to manage feedback.
    """

    has_score = False
    STUDENT_FILEUPLOAD_MAX_SIZE = 4 * 1000 * 1000  # 4 MB

    display_name = String(
        scope=Scope.settings,
        default='Feedback',
        help="This name appears in the horizontal navigation at the top of the page."
    )

    pre_feedback_text = String(
        scope=Scope.settings,
        display_name="Text before feedback publish",
        default='Your report will appear here when ready',
        help=("The text visible to the student before feedback is published.")
    )

    post_feedback_text = String(
        scope=Scope.settings,
        display_name="Text after feedback publish",
        default='Here is your personalized report',
        help=("The text visible to the student after feedback is published.")
    )

    users_excluded_email = String(
        scope=Scope.settings,
        display_name="Users to exclude by email",
        default='',
        help="A list of email addresses of users that should not be shown. Wildcards are allowed, e.g. *.imd.org"
    )

    ########################################################
    feedback_text = String(
        scope=Scope.user_state,
        display_name="Instructor Feedback Text",
        default='',
        help=("Feedback text given to the Student by the Instructor.")
    )

    ########################################################
    feedback_filename = String(
        scope=Scope.user_state,
        display_name="Feedback file name",
        default='',
        help=("Feedback file given to the Student by the Instructor.")
    )
    feedback_sha1 = String(
        scope=Scope.user_state,
        display_name="Feedback File SHA1",
        default=None,
        help=("Feedback file SHA1.")
    )
    feedback_mimetype = String(
        scope=Scope.user_state,
        display_name="Feedback File MIME type",
        default=None,
        help="Feedback file MIME type."
    )
    feedback_timestamp = DateTime(
        scope=Scope.user_state,
        display_name="Feedback File Timestamp",
        default=None,
        help="Feedback file upload time."
    )

    ########################################################
    feedback_video = Dict(
        scope=Scope.user_state,
        display_name="Instructor Feedback Video",
        default=None,
        help="Feedback Video given to the Student by the Instructor"
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

    feedback_published = Boolean(
        scope=Scope.user_state,
        display_name="Feedback is published",
        default=False,
        help=("Indicates whether the feedback has been published.")
    )

    def student_view(self, context=None):
        # pylint: disable=no-member
        """
        The primary view of the FeedbackXBlock.
        """

        context = {
            "student_state": json.dumps(self.student_state()),
            "id": self.location.name.replace('.', '_'),
        }
        if self.show_staff_ui:
            context['show_staff_ui'] = True
            self.update_staff_debug_context(context)

        html = self.render_template('static/html/feedback.html', context)

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/css/feedback.css"))

        frag.add_javascript(self.resource_string("static/js/vendor/easyxdm/easyXDM.debug.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/jquery.tablesorter.min.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/CryptoJS/core-min.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/CryptoJS/enc-utf16-min.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/CryptoJS/enc-base64-min.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/CryptoJS/md5.js"))
        frag.add_javascript(self.resource_string("static/js/vendor/CryptoJS/tripledes.js"))

        # videojs
        frag.add_css_url("https://vjs.zencdn.net/5.8.0/video-js.css")
        frag.add_javascript_url("https://vjs.zencdn.net/ie8/1.1.2/videojs-ie8.min.js")
        frag.add_javascript_url("https://vjs.zencdn.net/5.8.0/video.js")

        frag.add_javascript(self.resource_string("static/js/imd.leanmodal.js"))
        frag.add_javascript(self.resource_string("static/js/kvcreator.js"))
        frag.add_javascript(self.resource_string("static/js/feedback.js"))

        frag.initialize_js('FeedbackXBlock')
        return frag

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
            return Template('{{ comment|urlize|linebreaks }}').render(Context({ "comment": comment }))
        else:
            return ''

    def student_state(self):
        """
        Returns a JSON serializable representation of student's state for
        rendering in client view.
        """

        self.updateFeedbackVideoUrls()

        return {
            'display_name': self.display_name,
            'pre_feedback_text': self.pre_feedback_text,
            'post_feedback_text': self.post_feedback_text,
            'feedback_text': self.feedback_text,
            'feedback_text_html': self.renderable_comment(self.feedback_text),
            'feedback_filename': self.feedback_filename,
            'feedback_mimetype': self.feedback_mimetype,
            'feedback_video': self.feedback_video,
            'feedback_published': self.feedback_published,
            'course_is_cohorted': self.is_course_cohorted(self.course_id)
        }

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
                    (cls.pre_feedback_text, 'String', 'string'),
                    (cls.post_feedback_text, 'String', 'string'),
                    (cls.email_subject, 'String', 'string'),
                    (cls.email_body, 'TextArea', 'string'),
                    (cls.users_excluded_email, 'TextArea', 'string'),
                )
            )

            context = {
                'fields': edit_fields
            }
            html = self.render_template('static/html/feedback_edit.html', context)

            fragment = Fragment(html)
            fragment.add_javascript(self.resource_string("static/js/feedback_edit.js"))
            fragment.initialize_js('FeedbackXBlock')
            return fragment
        except:  # pragma: NO COVER
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

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

    def feedback_data(self):
        """
        Returns student feedback data
        """
        def get_student_feedback_data():
            # pylint: disable=no-member
            """
            Returns feedback data for all students on the course.
            """
            try:
                regexp_string = self.regexp_from_users_excluded_email(self.users_excluded_email)
                re.compile(regexp_string)
                users = self.students_for_course(regexp_string)
            except:
                log.info("regexp is invalid: '%s', getting all students instead", regexp_string)
                users = self.students_for_course()

            for user in users:
                student_id = anonymous_id_for_user(user, self.course_id)
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
                        "StudentModule Init for course:%s module:%s student:%s  ",
                        module.course_id,
                        module.module_state_key,
                        module.student.username
                    )

                state = json.loads(module.state)
                feedback_text = state.get('feedback_text') or ''
                feedback_text_html = self.renderable_comment(feedback_text)
                feedback_filename = state.get('feedback_filename')
                feedback_video = state.get('feedback_video')
                if (feedback_video and 'added_on' in feedback_video):
                    date_added_obj = datetime.datetime.strptime(feedback_video['added_on'], DateTime.DATETIME_FORMAT)
                    feedback_video['added_on'] = format_date_time(date_added_obj)
                feedback_published = state.get('feedback_published')

                cohort_name = None
                if (self.is_course_cohorted(self.course_id)):
                    cohort_name = self.get_cohort(user, self.course_id).name

                yield {
                    'module_id': module.id,
                    'student_id': student_id,
                    'username': module.student.username,
                    'fullname': module.student.profile.name,
                    'feedback_text': feedback_text,
                    'feedback_text_html': feedback_text_html,
                    'feedback_filename': feedback_filename,
                    'feedback_video': feedback_video,
                    'feedback_published': feedback_published,
                    'cohort_name': cohort_name,
                    'email': module.student.email,
                }

        return {
            'student_feedback_list': list(get_student_feedback_data()),
            'display_name': self.display_name,
            'course_is_cohorted': self.is_course_cohorted(self.course_id),
            'email_subject': self.email_subject,
            'email_body': self.email_body,
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

    @XBlock.handler
    def get_feedback_data(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return feedback data
        """
        require(self.is_course_staff)
        return Response(json_body=self.feedback_data())

    @XBlock.json_handler
    def update_feedback_text(self, data, suffix=''):
        """
        Update feedback text.
        """
        require(self.is_course_staff)
        module = StudentModule.objects.get(pk=data['module_id'])
        state = json.loads(module.state)
        state['feedback_text'] = data['feedback_text']
        module.state = json.dumps(state)
        module.save()
        log.info(
            "update_feedback_text for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.feedback_data())

    @XBlock.handler
    def feedback_file_upload(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Save feedback file.
        """
        require(self.is_course_staff)
        upload = request.params['feedback-file']
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        state['feedback_sha1'] = sha1 = _get_sha1(upload.file)
        state['feedback_filename'] = filename = upload.file.name
        state['feedback_mimetype'] = mimetypes.guess_type(upload.file.name)[0]
        state['feedback_timestamp'] = _now().strftime(
            DateTime.DATETIME_FORMAT
        )
        path = self._file_storage_path(sha1, filename)
        if not default_storage.exists(path):
            default_storage.save(path, File(upload.file))
        module.state = json.dumps(state)
        module.save()
        log.info(
            "feedback_file_upload for course:%s module:%s student:%s ",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.feedback_data())

    @XBlock.handler
    def staff_download_feedback_file(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return feedback file url for a given student.
        """
        require(self.is_course_staff)
        module = StudentModule.objects.get(pk=request.params['module_id'])
        state = json.loads(module.state)
        path = self._file_storage_path(
            state['feedback_sha1'],
            state['feedback_filename']
        )
        return self.download(
            path,
            state['feedback_mimetype'],
            state['feedback_filename'],
            require_staff=True
        )

    @XBlock.handler
    def student_download_feedback_file(self, request, suffix=''):
        # pylint: disable=unused-argument
        """
        Return feedback file url for the logged in student.
        """
        as_attachment = 'as_attachment' not in request.params or request.params['as_attachment'] != '0'
        path = self._file_storage_path(
            self.feedback_sha1,
            self.feedback_filename,
        )
        return self.download(
            path,
            self.feedback_mimetype,
            self.feedback_filename,
            as_attachment = as_attachment
        )

    def download(self, path, mime_type, filename, require_staff=False, as_attachment=True):
        """
        Return a file from storage and return in a Response.
        """
        try:
            file_descriptor = default_storage.open(path)
            app_iter = iter(partial(file_descriptor.read, BLOCK_SIZE), '')
            if (as_attachment):
                return Response(
                    app_iter=app_iter,
                    content_type=mime_type,
                    content_disposition="attachment; filename=" + filename.encode('utf-8'))
            else:
                return Response(
                    app_iter=app_iter,
                    content_type=mime_type)
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

    ########################################################
    # Video handlers
    ########################################################

    @XBlock.json_handler
    def add_feedback_video(self, data, suffix=''):
        """
        Save video feedback from staff.
        """
        require(self.is_course_staff)

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

            return Response(json_body=self.feedback_data())

    @XBlock.json_handler
    def fetch_feedback_video_urls(self, data, suffix=''):
        """
        Updates the feedback video urls for a student, and returns them.
        """
        require(self.is_course_staff)

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
        require(self.is_course_staff)
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
        return Response(json_body=self.feedback_data())

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

    ########################################################

    @XBlock.json_handler
    def publish_feedback(self, data, suffix=''):
        """
        Publish or unpublish feedback.
        """
        require(self.is_course_staff)
        module = StudentModule.objects.get(pk=data['module_id'])
        state = json.loads(module.state)
        state['feedback_published'] = data['feedback_published']
        module.state = json.dumps(state)
        module.save()
        log.info(
            "publish for course:%s module:%s student:%s",
            module.course_id,
            module.module_state_key,
            module.student.username
        )
        return Response(json_body=self.feedback_data())

    @XBlock.json_handler
    def save_feedback(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Persist block data when updating settings in studio.
        """
        self.display_name = data.get('display_name', self.display_name)
        self.pre_feedback_text = data.get('pre_feedback_text', self.pre_feedback_text)
        self.post_feedback_text = data.get('post_feedback_text', self.post_feedback_text)
        self.email_subject = data.get('email_subject', self.email_subject)
        self.email_body = data.get('email_body', self.email_body)

        users_excluded_email = data.get('users_excluded_email', self.users_excluded_email)
        try:
            regexp_string = self.regexp_from_users_excluded_email(users_excluded_email)
            re.compile(regexp_string)
        except:
            raise JsonHandlerError(400, 'Users to exclude by email is causing an error, please edit.')
        self.users_excluded_email = users_excluded_email

    def logged_in_username(self):
        loggedInUser = User.objects.get(id=self.scope_ids.user_id)
        return loggedInUser.username

    @property
    def is_course_staff(self):
        # pylint: disable=no-member
        """
        Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    @property
    def in_studio_preview(self):
        """
        Check whether we are in Studio preview mode.
        """
        # When we're running in Studio Preview mode, the XBlock won't provide us with a user ID.
        # (Note that `self.xmodule_runtime` will still provide an anonymous
        # student ID, so we can't rely on that)
        return self.scope_ids.user_id is None

    @property
    def show_staff_ui(self):
        """
        Returns True if current user is staff and not in studio.
        """
        return self.is_course_staff and not self.in_studio_preview

    def render_template(self, template_path, context={}):
        """
        Evaluate a template by resource path, applying the provided context
        """
        template_str = self.resource_string(template_path)
        return Template(template_str).render(Context(context))

    def resource_string(self, resource_path):
        """
        Gets the content of a resource
        """
        resource_content = pkg_resources.resource_string(__name__, resource_path)
        return resource_content.decode("utf8")

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


def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied

def format_date_time(dateTime):
    return dateTime.strftime('%b %d %Y %H:%M (UTC)')

def _get_sha1(file_descriptor):
    """
    Get file hex digest (fingerprint).
    """
    sha1 = hashlib.sha1()
    for block in iter(partial(file_descriptor.read, BLOCK_SIZE), ''):
        sha1.update(block)
    file_descriptor.seek(0)
    return sha1.hexdigest()

def _now():
    """
    Get current date and time.
    """
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
