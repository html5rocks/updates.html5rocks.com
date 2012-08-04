from google.appengine.ext import blobstore
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
import logging
import urllib

class ImageHandler(blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, image_id):
    image_id = str(urllib.unquote(image_id))
    if not blobstore.get(image_id):
      self.error(404)
    else:
      self.send_blob(image_id)

def main():
    application = webapp.WSGIApplication(
          [('/images/(.*)', ImageHandler),
          ], debug=True)
    run_wsgi_app(application)

if __name__ == '__main__':
  main()
