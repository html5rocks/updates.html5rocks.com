HTML5Rocks Update Stream

INTRO
====

An instance of Nick Johnson's Bloggart (https://github.com/Arachnid/bloggart)
customised for HTML5Rocks by Michael Mahemoff. The only customisations
are a new theme - see "themes/html5Rocks" - and config.py. No core code
has been forked; thus, it should be possible to update the project later on.

SETUP
====
* Simply host this project on App Engine.
* Hit <url>/admin/ to log in and make/manage content.
  [BTW that's /admin/ <---- Note the trailing slash]

DEV/DEBUGGING TIPS
==================
* Whenever you change the theme, you will need to visit
  /admin/ to regenerate (or clear the data store as below,
  but you'll also lose any dummy posts).

* It's often convenient to run the server with:
    dev_appserver.py --clear_datastore .
  ... as the posts are stored in the datastore, this will clear them.

