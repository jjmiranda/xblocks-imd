"""TO-DO: Write a description of what this XBlock is."""

import pkg_resources
import logging
import json
import requests
import datetime
import pytz
import time
import re

from django.template import Context, Template
from django.contrib.auth.models import User

from xblock.core import XBlock
from xblock.fields import Scope, String, DateTime, Float, Integer
from xblock.fragment import Fragment
from xblock.exceptions import JsonHandlerError

from courseware.models import StudentModule

log = logging.getLogger(__name__)

class KVXBlock(XBlock):
    """
    This xblock records a user's profile video to Kulu Valley.
    """
    has_score = True

    display_name = String(
        display_name="Display Name",
        default="Profile Videos",
        scope=Scope.settings,
        help="This name appears in the horizontal navigation at the top of the page."
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
        display_name="Score",
        help=("Grade score given to assignment by staff."),
        default=1,
        scope=Scope.settings
    )
    users_excluded_email = String(
        scope=Scope.settings,
        display_name="Users to exclude by email",
        default='',
        help="A list of email addresses of users that should not be shown. Wildcards are allowed, e.g. *.imd.org"
    )

    video_mp4_url = String(
        display_name="Video mp4 URL",
        default='',
        scope=Scope.user_state,
        help="Video mp4 URL"
    )

    ########################################################
    video_kulu_id = String(
        display_name="Video kulu id",
        default='',
        scope=Scope.user_state,
        help="Video kulu id"
    )
    video_hls_url = String(
        display_name="Video HLS URL",
        default='',
        scope=Scope.user_state,
        help="Video HLS URL"
    )
    video_thumbnail_url = String(
        display_name="Video Thumbnail URL",
        default='',
        scope=Scope.user_state,
        help="Video Thumbnail URL"
    )
    video_date_created = DateTime(
        display_name="Video Creation Date",
        default=None,
        scope=Scope.user_state,
        help="Video Creation Date"
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

    def student_view(self, context=None):
        """
        The primary view of the KVXBlock, shown to students
        when viewing courses.
        """

        self.updateStudentVideoUrls()
        context = {
            'not_in_studio': not self.is_in_studio(),
            'display_name': self.display_name,
            'video_kulu_id': none_to_empty(self.video_kulu_id),
            'video_mp4_url': none_to_empty(self.video_mp4_url),
            'video_hls_url': none_to_empty(self.video_hls_url),
            'video_thumbnail_url': none_to_empty(self.video_thumbnail_url),
            'video_date_created': date_handler(self.video_date_created),
            'video_icon_url': self.runtime.local_resource_url(self, 'public/images/video.png'),
            'ascending_sort_icon_url': self.runtime.local_resource_url(self, 'public/images/down.png'),
            'descending_sort_icon_url': self.runtime.local_resource_url(self, 'public/images/up.png')
        }

        frag = Fragment()
        frag.add_content(
            render_template(
                'static/html/kvxblock.html',
                context
            )
        )

        frag.add_css(load_resource("static/css/kvxblock.css"))

        frag.add_javascript(load_resource("static/js/vendor/easyxdm/easyXDM.debug.js"))
        frag.add_javascript(load_resource("static/js/vendor/URI.js"))
        frag.add_javascript(load_resource("static/js/vendor/jquery.ui.touch-punch.min.js")) # required for shapeshift on mobile
        frag.add_javascript(load_resource("static/js/vendor/jquery.shapeshift.min.js"))
        frag.add_javascript(load_resource("static/js/vendor/CryptoJS/core-min.js"))
        frag.add_javascript(load_resource("static/js/vendor/CryptoJS/enc-utf16-min.js"))
        frag.add_javascript(load_resource("static/js/vendor/CryptoJS/enc-base64-min.js"))
        frag.add_javascript(load_resource("static/js/vendor/CryptoJS/md5.js"))
        frag.add_javascript(load_resource("static/js/vendor/CryptoJS/tripledes.js"))

        # videojs
        frag.add_css_url("https://vjs.zencdn.net/5.8.0/video-js.css")
        frag.add_javascript_url("https://vjs.zencdn.net/ie8/1.1.2/videojs-ie8.min.js")
        frag.add_javascript_url("https://vjs.zencdn.net/5.8.0/video.js")

        frag.add_javascript(load_resource("static/js/src/kvcreator.js"))
        frag.add_javascript(load_resource("static/js/src/kvxblock.js"))

        frag.initialize_js('KVXBlock')
        return frag

    def studio_view(self, context=None):
        """
        Return fragment for editing block in studio.
        """
        try:
            cls = type(self)

            edit_fields = (
                (field, type, none_to_empty(getattr(self, field.name)), validator)
                for field, type, validator in (
                    (cls.display_name, 'String', 'string'),
                    (cls.points, 'Integer', 'number'),
                    (cls.weight, 'Float', 'number'),
                    (cls.users_excluded_email, 'TextArea', 'string'),
                )
            )

            context = {
                'fields': edit_fields
            }
            html = render_template('static/html/kvxblockedit.html', context)
            fragment = Fragment(html)
            fragment.add_javascript(load_resource("static/js/src/kvxblockedit.js"))
            fragment.initialize_js('kvXBlockInitStudio')
            return fragment
        except:  # pragma: NO COVER
            log.error("Don't swallow my exceptions", exc_info=True)
            raise

    @XBlock.json_handler
    def save_kvxblock(self, data, suffix=''):
        # pylint: disable=unused-argument
        """
        Persist xblock data when updating settings in studio.
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

        users_excluded_email = data.get('users_excluded_email', self.users_excluded_email)
        try:
            regexp_string = self.regexp_from_users_excluded_email(users_excluded_email)
            re.compile(regexp_string)
        except:
            raise JsonHandlerError(400, 'Users to exclude by email is causing an error, please edit.')
        self.users_excluded_email = users_excluded_email

    ########################################################
    # Video handlers
    ########################################################

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

    def get_videos(self):
        regexp = None
        try:
            regexp_string = self.regexp_from_users_excluded_email(self.users_excluded_email)
            if (len(regexp_string)):
                regexp = re.compile(regexp_string)
        except:
            log.info("regexp is invalid: '%s', showing all students instead", regexp_string)

        modules = StudentModule.objects.filter(module_state_key=self.location)
        userVideos = []
        for module in modules:
            moduleState = json.loads(module.state)
            # log.info('moduleState = {}'.format(moduleState))
            user = User.objects.get(id=module.student_id)
            if regexp and regexp.match(user.email):
                continue

            userName = user.username
            try:
                if ('video_kulu_id' in moduleState):
                    video_kulu_id = moduleState['video_kulu_id']
                if (len(video_kulu_id) > 0):
                    dateCreated = ''
                    dateCreatedIso = ''
                    try:
                        if (moduleState['video_date_created']):
                            dateCreatedObj = datetime.datetime.strptime(moduleState['video_date_created'], DateTime.DATETIME_FORMAT)
                            dateCreated = date_handler(dateCreatedObj)
                            dateCreatedIso = dateCreatedObj.isoformat()
                    except:
                        pass

                    video_mp4_url = moduleState['video_mp4_url']
                    video_hls_url = moduleState['video_hls_url']

                    if (video_mp4_url is None or video_hls_url is None):
                        try:
                            mp4_url, hls_url = self.get_video_urls(video_kulu_id, retry=False)
                            if (mp4_url and video_mp4_url is None) or (hls_url and video_hls_url is None):
                                video_mp4_url = moduleState['video_mp4_url'] = mp4_url
                                video_hls_url = moduleState['video_hls_url'] = hls_url
                                module.state = json.dumps(moduleState)
                                module.save()
                        except:
                            pass

                    userVideos.append({
                        'name': userName,
                        'video_mp4_url': video_mp4_url,
                        'video_hls_url': video_hls_url,
                        'video_thumbnail_url': moduleState['video_thumbnail_url'],
                        'video_date_created': dateCreated,
                        'video_date_created_iso': dateCreatedIso,
                        'video_kulu_id': video_kulu_id,
                    })
            except:
                pass
        return userVideos

    def updateStudentVideoUrls(self):
        if (self.video_kulu_id and
                (self.video_mp4_url is None or self.video_hls_url is None)):
            log.warning("student video is missing urls: kulu_id=%s mp4_url=%s, hls_url=%s",
                        self.video_kulu_id, self.video_mp4_url, self.video_hls_url)
            log.info(
                "updating student video for course:%s module:%s student:%s",
                self.course_id,
                self.location,
                self.logged_in_username()
            )
            try:
                mp4_url, hls_url = self.get_video_urls(self.video_kulu_id, retry=False)
                self.video_mp4_url = mp4_url
                self.video_hls_url = hls_url
            except:
                log.info('failed to update urls for kulu id %s', self.video_kulu_id)

    @XBlock.json_handler
    def get_all_videos(self, data, suffix=''):
        log.info(
            "get_all_videos for course:%s module:%s student:%s",
            self.course_id,
            self.location,
            self.logged_in_username()
        )
        return {
            'all_videos': json.dumps(self.get_videos())
        }

    @XBlock.json_handler
    def set_video_id(self, data, suffix=''):
        """
        Set the video url and thumbnail url from Kulu Valley.
        We first call a KV api to get the mp4/hls url.
        Calling with 'kulu_id' = '' deletes existing video.
        """
        kulu_id = data['kulu_id']

        def studentVideoData():
            return {
                'video_mp4_url': none_to_empty(self.video_mp4_url),
                'video_hls_url': none_to_empty(self.video_hls_url),
                'video_thumbnail_url': self.video_thumbnail_url,
                'video_date_created': date_handler(self.video_date_created),
                'video_kulu_id': self.video_kulu_id,
            }

        if (kulu_id and kulu_id != ''):
            template_kulu_valley_preview_url = "https://imd.kuluvalley.com/kulu/{}/thumbnail?v=18"
            thumbnail_url = template_kulu_valley_preview_url.format(kulu_id)

            self.video_kulu_id = kulu_id
            self.video_mp4_url = None
            self.video_hls_url = None
            self.video_thumbnail_url = thumbnail_url
            self.video_date_created = nowUTC()
            self.mark_as_done()
            log.info(
                "set_video_id for course:%s module:%s student:%s",
                self.course_id,
                self.location,
                self.logged_in_username()
            )
            try:
                mp4_url, hls_url = self.get_video_urls(kulu_id) # may not be available at this point
                self.video_mp4_url = mp4_url
                self.video_hls_url = hls_url
                return studentVideoData()
            except requests.exceptions.HTTPError as e:
                if (e.response.status_code == 404):
                    raise JsonHandlerError(404, 'video not found')
                else:
                    return studentVideoData()
            except:
                return studentVideoData()

        else:
            # Delete the video
            self.video_mp4_url = None
            self.video_hls_url = None
            self.video_thumbnail_url = None
            self.video_date_created = None
            self.video_kulu_id = None
            self.mark_as_not_done()
            return studentVideoData()

    def get_video_urls(self, kulu_id, retry=True):
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

            log.info("getting kulu valley urls")
            mp4_url, hls_url = fetch_kulu_urls(kulu_id)

            if retry:
                retry_count = 1
                max_retries = 1
                while (retry_count <= max_retries and (mp4_url is None or hls_url is None)):
                    log.info("getting kulu valley urls: retry %d", retry_count)
                    sleep_for = 2 ** (retry_count-1) # 1, 2, 4.. seconds
                    log.info("sleeping for %.1f seconds", sleep_for)
                    time.sleep(sleep_for)
                    mp4_url, hls_url = fetch_kulu_urls(kulu_id)
                    retry_count += 1

        return mp4_url, hls_url

    ########################################################


    def mark_as_done(self):
        """
        Mark the assignment as done for a this student.
        """
        grade_event = {'value': self.points, 'max_value': self.points}
        self.runtime.publish(self, 'grade', grade_event)

    def mark_as_not_done(self):
        """
        Mark the assignment as not done for a this student.
        """
        grade_event = {'value': 0, 'max_value': self.points}
        self.runtime.publish(self, 'grade', grade_event)

    def logged_in_username(self):
        loggedInUser = User.objects.get(id=self.scope_ids.user_id)
        return loggedInUser.username

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("KVXBlock",
             """<vertical_demo>
                <kvxblock/>
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

def nowUTC():
    """
    Get current date and time in UTC.
    """
    return datetime.datetime.now(pytz.utc)

date_handler = lambda obj: (
    obj.strftime('%d %b %Y %H:%M:%S')
    if isinstance(obj, datetime.datetime)
    or isinstance(obj, datetime.date)
    else None
)

def none_to_empty(data):
    return data if data is not None else ''
