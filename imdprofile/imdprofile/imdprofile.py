"""
An XBlock to show the profile of each student on the course.
"""

import logging
import pkg_resources
import json
import datetime
import pytz
import re

log = logging.getLogger(__name__)

from django.core.exceptions import PermissionDenied
from django.template import Context, Template
from django.contrib.auth.models import User

from xblock.core import XBlock
from xblock.fields import Scope, String, Boolean
from xblock.fragment import Fragment
from xblock.exceptions import JsonHandlerError

from student.models import anonymous_id_for_user


class IMDProfileXBlock(XBlock):
    """
    An XBlock to show the profile of each student on the course.
    """

    has_score = False

    display_name = String(
        scope=Scope.settings,
        default='Profile',
        help="This name appears in the horizontal navigation at the top of the page."
    )
    users_included_email = String(
        scope=Scope.settings,
        display_name="Users to include by email",
        default='',
        help="A list of email addresses of users that should be shown. Wildcards are allowed, e.g. *.imd.org"
    )
    profile_display_job_title = Boolean(
        scope=Scope.settings,
        display_name="Display Job Title in Profile",
        default=True,
        help="Display Job Title in Profile dialog (for all students)."
    )
    profile_display_organisation = Boolean(
        scope=Scope.settings,
        display_name="Display Organisation in Profile",
        default=True,
        help="Display Organisation in Profile dialog (for all students)."
    )
    profile_display_work_country = Boolean(
        scope=Scope.settings,
        display_name="Display Work Country in Profile",
        default=True,
        help="Display Work Country in Profile dialog (for all students)."
    )
    profile_display_email_button = Boolean(
        scope=Scope.settings,
        display_name="Display Email Button",
        default=True,
        help="Display Email button in Student grid and Profile dialog (for all students)."
    )
    profile_display_bio = Boolean(
        scope=Scope.settings,
        display_name="Display Biography in Profile",
        default=True,
        help="Display Biography in Profile dialog (for all students)."
    )
    enable_cohorts = Boolean(
        scope=Scope.settings,
        display_name="Enable Cohorts",
        default=False,
        help="Enable Cohorts selection."
    )

    def student_view(self, context=None):
        # pylint: disable=no-member
        """
        The primary view of the IMDProfileXBlock.
        """

        context = {
            'student_view_data': json.dumps(self.student_view_data()),
            'id': self.location.name.replace('.', '_'),
        }
        if self.show_staff_ui:
            context['show_staff_ui'] = True
            self.update_staff_debug_context(context)

        html = self.render_template('static/html/imdprofile.html', context)

        frag = Fragment(html)
        frag.add_css(self.resource_string("static/css/imdprofile.css"))
        # not using the minified version of shapeshift as it has a bug, see
        # https://github.com/McPants/jquery.shapeshift/issues/137
        frag.add_javascript(self.resource_string("static/js/vendor/jquery.shapeshift.js"))
        frag.add_javascript(self.resource_string("static/js/imd.leanmodal.js"))
        frag.add_javascript(self.resource_string("static/js/imdprofile.js"))

        frag.initialize_js('IMDProfileXBlock')
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
                    (cls.users_included_email, 'TextArea', 'string'),
                    (cls.profile_display_job_title, 'Boolean', 'number'),
                    (cls.profile_display_organisation, 'Boolean', 'number'),
                    (cls.profile_display_work_country, 'Boolean', 'number'),
                    (cls.profile_display_email_button, 'Boolean', 'number'),
                    (cls.profile_display_bio, 'Boolean', 'number'),
                    (cls.enable_cohorts, 'Boolean', 'number'),
                )
            )

            context = {
                'fields': edit_fields
            }
            html = self.render_template('static/html/imdprofile_edit.html', context)

            fragment = Fragment(html)
            fragment.add_javascript(self.resource_string("static/js/imdprofile_edit.js"))
            fragment.initialize_js('IMDProfileXBlock')
            return fragment
        except:  # pragma: NO COVER
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

    def regexp_from_users_included_email(self, users_included_email):
        regexp_string = ''
        emails = users_included_email.split('\n')
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

    def student_view_data(self):
        """
        Returns student view data
        """
        def get_student_profile_data():
            # pylint: disable=no-member
            """
            Returns profile data for all students on the course.
            """
            try:
                regexp_string = self.regexp_from_users_included_email(self.users_included_email)
                re.compile(regexp_string)
                users = self.students_for_course(regexp_string)
            except:
                log.info("regexp is invalid: '%s'", regexp_string)
                users = []

            for user in users:
                student_id = anonymous_id_for_user(user, self.course_id)
                profile = user.profile

                vip = self.get_vip(user)
                image_url = None
                if vip:
                    image_url = "https://my.imd.org/api/profile/{}/profile-picture-header".format(vip)
                else:
                    if self.is_course_staff:
                        image_url = self.runtime.local_resource_url(self, 'public/images/profile-picture-header-no-vip.gif')
                    else:
                        image_url = self.runtime.local_resource_url(self, 'public/images/profile-picture-header.gif')

                cohort_name = None
                if (self.is_course_cohorted(self.course_id)):
                    cohort_name = self.get_cohort(user, self.course_id).name

                yield {
                    'student_id': student_id,
                    'username': user.username,
                    'fullname': profile.name,
                    'vip': vip,
                    'image_url': image_url,
                    'email': user.email,
                    'cohort_name': cohort_name,
                }

        return {
            'student_profile_list': list(get_student_profile_data()),
            'display_name': self.display_name,
            'username': self.logged_in_username,
            'course_is_cohorted': self.enable_cohorts and self.is_course_cohorted(self.course_id),
            'profile_display': {
                'profile_display_job_title': self.profile_display_job_title,
                'profile_display_organisation': self.profile_display_organisation,
                'profile_display_work_country': self.profile_display_work_country,
                'profile_display_email_button': self.profile_display_email_button,
                'profile_display_bio': self.profile_display_bio,
            },
        }

    def students_for_course(self, regexp=None):
        students = []
        if regexp and len(regexp) > 0:
            students = User.objects.filter(
                is_active=True,
                courseenrollment__course_id=self.course_id,
                courseenrollment__is_active=True,
                email__iregex=regexp,
            ).order_by('profile__name')
        return students

    @XBlock.json_handler
    def save_profile(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Persist block data when updating settings in studio.
        """
        self.display_name = data.get('display_name', self.display_name)

        users_included_email = data.get('users_included_email', self.users_included_email)
        try:
            regexp_string = self.regexp_from_users_included_email(users_included_email)
            re.compile(regexp_string)
        except:
            raise JsonHandlerError(400, 'Users to exclude by email is causing an error, please edit.')
        self.users_included_email = users_included_email

        self.profile_display_job_title = data.get('profile_display_job_title', self.profile_display_job_title)
        self.profile_display_organisation = data.get('profile_display_organisation', self.profile_display_organisation)
        self.profile_display_work_country = data.get('profile_display_work_country', self.profile_display_work_country)
        self.profile_display_email_button = data.get('profile_display_email_button', self.profile_display_email_button)
        self.profile_display_bio = data.get('profile_display_bio', self.profile_display_bio)
        self.enable_cohorts = data.get('enable_cohorts', self.enable_cohorts)

    @property
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

    def get_vip(self, user):
        vip = None
        try:
            social_auth_uid = user.social_auth.filter(provider='tpa-saml')[0].uid
            if len(social_auth_uid) > 0:
                uid_parts = social_auth_uid.split(':')
                if (len(uid_parts) > 1):
                    vip = uid_parts[1]
        except Exception as socialExc:
            log.info(socialExc)
        return vip

def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied

def _now():
    """
    Get current date and time.
    """
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
