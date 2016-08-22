"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources
import json
import logging
import requests
import datetime
import pytz

from django.template import Context, Template
from django.contrib.auth.models import User

from social.apps.django_app.utils import load_strategy

from xblock.core import XBlock
from xblock.fields import Scope, String, DateTime, Float, Integer
from xblock.fragment import Fragment
from xblock.reference.user_service import XBlockUser, UserService
from xblock.exceptions import JsonHandlerError

from courseware.models import StudentModule

log = logging.getLogger(__name__)

class SurveyXBlock(XBlock):
    """
    TO-DO: document what your XBlock does.
    """

    # Fields are defined on the class.  You can access them in your code as
    # self.<fieldname>.

    display_name = String(
        display_name="Display Name",
        default="Survey module",
        scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of the page."
    )

    survey_id = String(
        display_name="Qualtrix survey id",
        value='',
        scope=Scope.settings,
        help="This is the identifier of the Qualtrix survey."
    )

    anonymousSurvey = Integer(
        display_name="Anonymous Survey",
        value = 0,
        scope = Scope.settings,
        helper = "Make this survey anonymous."
    )

    frameSizeHeight = Integer(
        display_name="Height of the survey frame",
        default = 600,
        scope = Scope.settings,
        helper = "Make the survey frame with adjastable height."
    )

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

    def is_in_studio(self):
        """
        Return true if in studio.
        """
        return getattr(self.xmodule_runtime, 'is_author_mode', False)

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")


    # def load_resource(self,resource_path):  # pragma: NO COVER
    #     """
    #     Gets the content of a resource
    #     """
    #     resource_content = pkg_resources.resource_string(__name__, resource_path)
    #     return unicode(resource_content)
    #
    #
    # def render_template(self, template_path, context=None):  # pragma: NO COVER
    #     """
    #     Evaluate a template by resource path, applying the provided context.
    #     """
    #     if context is None:
    #         context = {}
    #     template_str = self.load_resource(template_path)
    #     template = Template(template_str)
    #     return template.render(Context(context))

    # TO-DO: change this view to display your data your own way.
    def student_view(self, context=None):
        """
        The primary view of the SurveyXBlock, shown to students
        when viewing courses.
        """

        context = {
            "display_name" : self.display_name
        }

        html = render_template("static/html/surveymodule.html", context)
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/surveymodule.css"))
        frag.add_javascript(self.resource_string("static/js/src/surveymodule.js"))
        frag.initialize_js('SurveyXBlock')
        return frag

    def studio_view(self, context=None):
        try:

            context = {
                'surveyId': self.survey_id
            }
            context["displayName"] = self.display_name
            context["frameSizeHeight"] = self.frameSizeHeight

            html = render_template('static/html/surveymodule-std.html', context)
            fragment = Fragment(html)
            fragment.add_javascript(load_resource("static/js/src/surveymoduledit.js"))
            fragment.add_css(self.resource_string("static/css/surveymodule.css"))
            fragment.initialize_js('SurveyXBlockInitStudio')
            return fragment
        except Exception as e:  # pragma: NO COVER
            # log.error("Don't swallow my exceptions", exc_info=True)""
            log.info("%s",e)
            raise

    @XBlock.json_handler
    def logged_in_username(self, data, suffix=''):
        lUser = User.objects.get(id=self.scope_ids.user_id)

        jsonData = {}
        jsonData["userid"] = str(lUser.id)
        jsonData["username"] = lUser.username
        jsonData["email"] = lUser.email
        jsonData["surveyId"] = self.survey_id
        jsonData["socialUserID"] = ""
        jsonData["frameSizeHeight"] = self.frameSizeHeight
        jsonData["isStuffMemeber"] = self.is_course_staff()
        # jsonData["loadingGifUrl"] = self.runtime.local_resource_url(self, 'public/images/ajax-loader.gif')

        try:
            social = lUser.social_auth.filter(provider='tpa-saml')[0]
            jsonData["socialUserID"] = social.uid
            jsonData["socialUserLegacyId"] = social.user_id
        except Exception as socialExc:
            log.info(socialExc)

        log.info(lUser.social_auth)
        loggedInUser=json.dumps(jsonData)

        return loggedInUser

    @XBlock.json_handler
    def save_surveyblock(self, data, suffix=''):
        """
        Persist xblock data when updating settings in studio.
        """
        self.survey_id = data.get('inputSurveyID', self.survey_id)
        self.display_name = data.get('inputDislpayName',self.display_name)
        self.frameSizeHeight = data.get('frameSizeHeight',self.frameSizeHeight)
        log.info("%s",self.survey_id)

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("SurveyXBlock",
             """<surveymodule/>
             """),
            ("Multiple SurveyXBlock",
             """<vertical_demo>
                <surveymodule/>
                <surveymodule/>
                <surveymodule/>
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

def load_resource(resource_path):  # pragma: NO COVER
    """
    Gets the content of a resource
    """
    resource_content = pkg_resources.resource_string(__name__, resource_path)
    return resource_content.decode("utf8")
