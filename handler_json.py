import os

from django.utils import simplejson
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import fix_path
import models
import utils


class BaseHandler(webapp.RequestHandler):
  # def render_to_response(self, template_name, template_vals=None, theme=None):
  #   if not template_vals:
  #     template_vals = {}
  #   template_vals.update({
  #       'path': self.request.path,
  #       'handler_class': self.__class__.__name__,
  #       'is_admin': True,
  #   })
  #   template_name = os.path.join("admin", template_name)
  #   self.response.out.write(
  #       utils.render_template(template_name, template_vals, theme))
  pass


class JSONHandler(BaseHandler):

  def get(self):

    posts = models.BlogPost.all().order('-published').fetch(None) # all posts

    data = []
    for p in posts:
      data.append({
        'title': p.title,
        'author_id': p.author_id,
        'description': unicode(p.description),
        'updated': unicode(p.updated),
        'published': unicode(p.published),
        'path': p.path,
        })

    # Add CORS and Chrome Frame to response.
    self.response.headers.add_header('Access-Control-Allow-Origin', '*')
    self.response.headers.add_header('X-UA-Compatible', 'IE=Edge,chrome=1')
    self.response.headers['Content-Type'] = 'application/json'

    #return self.response.out.write(
    #    simplejson.dumps([entity.to_dict() for entity in posts]))
    return self.response.out.write(simplejson.dumps(data))


application = webapp.WSGIApplication([
    ('/.*', JSONHandler),
    ])


def main():
  fix_path.fix_sys_path()
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
