from __future__ import with_statement
from google.appengine.api import files

import datetime
import logging
import os
import re
import urllib2

from google.appengine.ext import deferred
from google.appengine.ext import webapp

import config
import markup
import models
import post_deploy
import utils

from django import newforms as forms
from django.utils import simplejson
from google.appengine.ext.db import djangoforms

import common # html5rocks common
from google.appengine.api import urlfetch
from google.appengine.api import users

class PostForm(djangoforms.ModelForm):
  # log = logging.getLogger()
  title = forms.CharField(widget=forms.TextInput(attrs={'id':'name'}))
  body = forms.CharField(widget=forms.Textarea(attrs={
      'id':'message',
      'rows': 10,
      'cols': 20}))
  body_markup = forms.ChoiceField(
    choices=[(k, v[0]) for k, v in markup.MARKUP_MAP.iteritems()])
  tags = forms.CharField(widget=forms.Textarea(attrs={'rows': 5, 'cols': 20}))
  draft = forms.BooleanField(required=False)
  image_url = forms.CharField(required=False, widget=forms.TextInput(attrs={'id':'image_url'}))

  if common.PROD:
    url = '%s/api/authors' % (config.main_site_origin)
  else:
    url = '%s/api/authors' % (config.main_site_test_origin)

  sorted_profiles = []
  try:
    response = urlfetch.fetch(url)
    if response.status_code == 200:
      sorted_profiles = simplejson.loads(response.content).keys()
  except urlfetch.DownloadError:
    pass

  author_id = forms.ChoiceField(
    choices=[(id,id) for id in sorted_profiles])
  IMAGE_STYLES = (('top','top'), ('left','left'), ('right','right'))
  image_style = forms.ChoiceField(required=False, choices=IMAGE_STYLES)
  class Meta:
    model = models.BlogPost
    fields = [ 'title', 'body', 'tags', 'author_id', 'image_url', 'image_style' ]

def with_post(fun):
  def decorate(self, post_id=None):
    post = None
    if post_id:
      post = models.BlogPost.get_by_id(int(post_id))
      if not post:
        self.error(404)
        return
    fun(self, post)
  return decorate


class BaseHandler(webapp.RequestHandler):
  def render_to_response(self, template_name, template_vals=None, theme=None):
    if not template_vals:
      template_vals = {}
    template_vals.update({
        'path': self.request.path,
        'handler_class': self.__class__.__name__,
        'is_admin': True,
    })
    template_name = os.path.join("admin", template_name)
    self.response.out.write(utils.render_template(template_name, template_vals,
                                                  theme))


class AdminHandler(BaseHandler):
  def get(self):
    offset = int(self.request.get('start', 0))
    count = int(self.request.get('count', 20))
    posts = models.BlogPost.all().order('-published').fetch(count, offset)
    template_vals = {
        'offset': offset,
        'count': count,
        'last_post': offset + len(posts) - 1,
        'prev_offset': max(0, offset - count),
        'next_offset': offset + count,
        'posts': posts,
    }
    self.render_to_response("index.html", template_vals)


class PostHandler(BaseHandler):
  def render_form(self, form):
    self.render_to_response("edit.html", {'form': form})

  @with_post
  def get(self, post):
    likely_profile_id = re.sub(r'@.*', '', users.get_current_user().nickname())
    self.render_form(PostForm(
        instance=post,
        initial={
          'draft': post and not post.path,
          'body_markup': post and post.body_markup or config.default_markup,
          'image_style': post and post.image_style or config.default_image_style,
          'author_id': post and post.author_id or likely_profile_id
        }))

  @with_post
  def post(self, post):
    form = PostForm(data=self.request.POST, instance=post,
                    initial={'draft': post and post.published is None})
    if form.is_valid():

      post = form.save(commit=False)

      image_url = form.clean_data['image_url']
      if image_url:
        try:
          u = urllib2.urlopen(image_url)
          file_name = files.blobstore.create(mime_type='image/jpeg')
          with files.open(file_name, 'a') as f:
            f.write(u.read())
          files.finalize(file_name)
          post.image_id = str(files.blobstore.get_blob_key(file_name))
        except:
          # Not sure how to use ErrorList in Django 0.96
          # form._errors['image'] = ''
          self.render_form(form)
          return
      if form.clean_data['draft']:# Draft post
        post.published = datetime.datetime.max
        post.put()
      else:
        if not post.path: # Publish post
          post.updated = post.published = datetime.datetime.now()
        else:# Edit post
          post.updated = datetime.datetime.now()
        post.publish()
      self.render_to_response("published.html", {
          'post': post,
          'draft': form.clean_data['draft']})
    else:
      self.render_form(form)

class DeleteHandler(BaseHandler):
  @with_post
  def post(self, post):
    if post.path:# Published post
      post.remove()
    else:# Draft
      post.delete()
    self.render_to_response("deleted.html", None)


class PreviewHandler(BaseHandler):
  @with_post
  def get(self, post):
    # Temporary set a published date iff it's still
    # datetime.max. Django's date filter has a problem with
    # datetime.max and a "real" date looks better.
    if post.published == datetime.datetime.max:
      post.published = datetime.datetime.now()
    self.response.out.write(utils.render_template('post.html', {
        'post': post,
        'is_admin': True}))


class RegenerateHandler(BaseHandler):
  def post(self):
    deferred.defer(post_deploy.PostRegenerator().regenerate)
    deferred.defer(post_deploy.PageRegenerator().regenerate)
    deferred.defer(post_deploy.try_post_deploy, force=True)
    self.render_to_response("regenerating.html")


class PageForm(djangoforms.ModelForm):
  path = forms.RegexField(
    widget=forms.TextInput(attrs={'id':'path'}), 
    regex='(/[a-zA-Z0-9/]+)')
  title = forms.CharField(widget=forms.TextInput(attrs={'id':'title'}))
  template = forms.ChoiceField(choices=config.page_templates.items())
  body = forms.CharField(widget=forms.Textarea(attrs={
      'id':'body',
      'rows': 10,
      'cols': 20}))
  class Meta:
    model = models.Page
    fields = [ 'path', 'title', 'template', 'body' ]

  def clean_path(self):
    data = self._cleaned_data()['path']
    existing_page = models.Page.get_by_key_name(data)
    if not data and existing_page:
      raise forms.ValidationError("The given path already exists.")
    return data


class PageAdminHandler(BaseHandler):
  def get(self):
    offset = int(self.request.get('start', 0))
    count = int(self.request.get('count', 20))
    pages = models.Page.all().order('-updated').fetch(count, offset)
    template_vals = {
        'offset': offset,
        'count': count,
        'prev_offset': max(0, offset - count),
        'next_offset': offset + count,
        'last_page': offset + len(pages) - 1,
        'pages': pages,
    }
    self.render_to_response("indexpage.html", template_vals)


def with_page(fun):
  def decorate(self, page_key=None):
    page = None
    if page_key:
      page = models.Page.get_by_key_name(page_key)
      if not page:
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('404 :(\n' + page_key)
        #self.error(404)
        return
    fun(self, page)
  return decorate

    
class PageHandler(BaseHandler):
  def render_form(self, form):
    self.render_to_response("editpage.html", {'form': form})

  @with_page
  def get(self, page):      
    self.render_form(PageForm(
        instance=page,
        initial={
          'path': page and page.path or '/',
        }))

  @with_page
  def post(self, page):
    form = None
    # if the path has been changed, create a new page
    if page and page.path != self.request.POST['path']:
      form = PageForm(data=self.request.POST, instance=None, initial={})
    else:
      form = PageForm(data=self.request.POST, instance=page, initial={})
    if form.is_valid():
      oldpath = form._cleaned_data()['path']
      if page:
        oldpath = page.path
      page = form.save(commit=False)
      page.updated = datetime.datetime.now()
      page.publish()
      # path edited, remove old stuff
      if page.path != oldpath:
        oldpage = models.Page.get_by_key_name(oldpath)
        oldpage.remove()
      self.render_to_response("publishedpage.html", {'page': page})
    else:
      self.render_form(form)


class PageDeleteHandler(BaseHandler):
  @with_page
  def post(self, page):
    page.remove()
    self.render_to_response("deletedpage.html", None)

