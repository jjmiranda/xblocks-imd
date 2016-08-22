"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources
import json
import logging
import requests
import datetime
import pytz
import collections
import re

from django.template import Context, Template
from django.contrib.auth.models import User

from social.apps.django_app.utils import load_strategy
from django.core.exceptions import PermissionDenied

from xblock.core import XBlock
from xblock.fields import Scope, String, DateTime, Float, Boolean, Integer
from xblock.fragment import Fragment
from xblock.reference.user_service import XBlockUser, UserService
from xblock.exceptions import JsonHandlerError

from courseware.models import StudentModule
from student.tests.factories import UserFactory

from student.models import user_by_anonymous_id
from submissions import api as submissions_api
from submissions.models import StudentItem

BLOCK_SIZE = 8 * 1024


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

log = logging.getLogger(__name__)

class SystemLoggerXBlock(XBlock):
    """
    TO-DO: document what your XBlock does.
    """

    # Fields are defined on the class.  You can access them in your code as
    # self.<fieldname>.

    # TO-DO: delete count, and define your own fields.
    display_name = String(
        display_name="Display Name",
        default="System info",
        scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of the page."
    )

    DisplayUserStats = Boolean(
        scope=Scope.settings,
        display_name="Display statistics to the student",
        default=True,
        help="Indicates whether the the statistics to the certain student will appear on his/her view."
    )

    EmailsListToFilter = String(
        scope=Scope.settings,
        display_name="Users to exclude by email",
        default='',
        help="A list of email addresses of users that should not be shown. Wildcards are allowed, e.g. *.imd.org"
    )

    FilterIMDUsers = Boolean(
        display_name="Flag to filter internal IMD users",
        default=False,
        scope=Scope.settings,
        help="Filter IMD users flag."
    )

    UserBrowserData = String(
        display_name="Browser version",
        default=None,
        scope=Scope.user_state,
        help="Help info."
    )

    UserSystemData = String(
        display_name="System version",
        default=None,
        scope=Scope.user_state,
        help="Help info."
    )

    UserFlashData = String(
        display_name="Flash version",
        default=None,
        scope=Scope.user_state,
        help="Help info."
    )

    UserErrorData = Boolean(
        display_name="Has browser error",
        default=False,
        scope=Scope.user_state,
        help="Error flag."
    )

    LastUserAccess = DateTime(
        display_name="Lass user access",
        scope=Scope.user_state,
        default=None,
        help="When the user accessed the system for the last time."
    )

    def logged_in_username(self):
        loggedInUser = User.objects.get(id=self.scope_ids.user_id)
        return loggedInUser.username

    @property
    def show_staff_ui(self):
        """
        Returns True if current user is staff and not in studio.
        """
        return self.is_course_staff

    @property
    def is_course_staff(self):
        # pylint: disable=no-member
        """
        Check if user is course staff.
        """
        return getattr(self.xmodule_runtime, 'user_is_staff', False)

    @reify
    def block_id(self):
        """
        Return the usage_id of the block.
        """
        return self.scope_ids.usage_id

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

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

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the SystemLoggerXBlock, shown to students
        when viewing courses.
        """
        context['show_staff_button'] = "none"
        context['display_user_stats'] = "none"
        context['displayName'] = self.display_name
        if self.show_staff_ui:
            context['show_staff_button'] = "inline"
        if self.DisplayUserStats:
            context['display_user_stats'] = "inline"

        html = render_template("static/html/systemlogger.html", context)
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/systemlogger.css"))
        frag.add_javascript(self.resource_string("static/js/src/jquery.tablesorter.min.js"))
        frag.add_javascript(self.resource_string("static/js/src/systemlogger.js"))
        frag.add_javascript(self.resource_string("static/js/src/swfobject.js"))
        frag.add_javascript(self.resource_string("static/js/src/moment.js"))
        frag.initialize_js('SystemLoggerXBlock')
        return frag


    def studio_view(self, context=None):
        try:

            context = {
                'displayName': self.display_name,
                'DisplayUserStats':self.DisplayUserStats,
                'EmailsListToFilter':self.EmailsListToFilter
            }

            html = render_template('static/html/systemloggedStudio.html', context)
            fragment = Fragment(html)
            fragment.add_javascript(load_resource("static/js/src/systemloggedStudio.js"))
            # fragment.add_javascript(self.resource_string("static/js/imd.leanmodal.js"))
            fragment.add_css(self.resource_string("static/css/systemlogger.css"))
            fragment.initialize_js('SystemLoggerStudioXBlock')

            return fragment
        except Exception as e:  # pragma: NO COVER
            # log.error("Don't swallow my exceptions", exc_info=True)""
            log.info("%s",e)
            raise

    @XBlock.json_handler
    def save_inputs(self, data, suffix=''):
        """
        Persist xblock data when updating settings in studio.
        """
        self.display_name = data.get('inputDislpayName',self.display_name)
        self.DisplayUserStats = data.get('DisplayUserStats', self.DisplayUserStats)
        self.EmailsListToFilter = data.get('EmailsListToFilter', self.EmailsListToFilter)
        # log.info("%s",self.FilterIMDUsers)

    # TO-DO: change this handler to perform your own actions.  You may need more
    # than one handler, or you may not need any handlers at all.
    @XBlock.json_handler
    def updateDetails(self, data, suffix=''):
        log.info('%s', data['browser'])
        self.UserBrowserData = data['browser']
        self.UserSystemData = data["osstring"]
        self.UserFlashData = data['flash']
        self.UserErrorData = data['browserError']
        self.LastUserAccess = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

    @XBlock.json_handler
    def readDetails(self, data, suffix=''):
        require(self.is_course_staff)
        regexString = self.regexp_from_users_excluded_email(self.EmailsListToFilter)
        users = self.students_for_course(regexString)
        strCourseID = str(self.course_id)
        returnData = []
        for user in users:
            sectionItem = {"UserName":user.username}
            sectionItem["CourseId"] = strCourseID
            sectionItem["UserId"] = user.id
            sectionItem["FullName"] = user.profile.name
            sectionItem["Browser"] = ""
            sectionItem["Flash"] = ""
            sectionItem["System"] = ""
            sectionItem["Error"] = False
            sectionItem["LastAccess"] = ""
            modules = StudentModule.objects.filter(module_state_key=self.location,student=user)
            for module in modules:
                moduleState = json.loads(module.state)
                # user = User.objects.get(id=module.student_id)
                # userName = user.username
                # log.info("%s",userName)
                # sectionItem = {"UserName":userName}
                # log.info("%s",module.student.profile.name)
                sectionItem["FullName"] = module.student.profile.name
                if(moduleState['UserBrowserData']):
                    userValue = moduleState['UserBrowserData']
                    sectionItem["Browser"] = userValue
                if(moduleState['UserFlashData']):
                    userFlash = moduleState['UserFlashData']
                    sectionItem["Flash"] = userFlash
                if(moduleState['UserSystemData']):
                    userSystem = moduleState['UserSystemData']
                    sectionItem["System"] = userSystem
                if(moduleState['UserErrorData']):
                    userError = moduleState['UserErrorData']
                    sectionItem["Error"] = userError
                if(moduleState['LastUserAccess']):
                    lastAccess = moduleState['LastUserAccess']
                    sectionItem["LastAccess"] = lastAccess

            returnData.append(sectionItem)
            # log.info(sectionItem)

        return returnData #{"result": "OK", "username":self.logged_in_username(), "data":"lastModuleState"}

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("SystemLoggerXBlock",
             """<systemlogger/>
             """),
            ("Multiple SystemLoggerXBlock",
             """<vertical_demo>
                <systemlogger/>
                <systemlogger/>
                <systemlogger/>
                </vertical_demo>
             """),
        ]

def render_template(template_path, context=None):  # pragma: NO COVER
    """
    Evaluate a template by resource path, applying the provided context.
    """
    if context is None:
        context = {}

    template_str = load_resource(template_path)
    template = Template(template_str)
    return template.render(Context(context))

def require(assertion):
    """
    Raises PermissionDenied if assertion is not true.
    """
    if not assertion:
        raise PermissionDenied

def load_resource(resource_path):  # pragma: NO COVER
    """
    Gets the content of a resource
    """
    resource_content = pkg_resources.resource_string(__name__, resource_path)
    return resource_content.decode("utf8")
