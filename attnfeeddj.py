#todo after -- have playlists expire from checking if there is no new tweet after a certain amount of time
import tweepy
import re
import json
import os
from flask import Flask, render_template, request, url_for
from flask_session import Session
from flask import Flask, session, request, redirect
import uuid
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired
from forms import FinishForm
import misc_util
import requests
import urllib.request
import urllib.parse
import urllib.error
import spotipy
import spotipy.util as util
from spotipy.oauth2 import SpotifyOAuth
from tinydb import TinyDB, Query
import shutil
import logging

app = Flask(__name__)

app.debug = False
user_db = TinyDB('.data/user_db.json')
playlist_searches_db = TinyDB('.data/playlist_searches_db.json')
twitter_db =  TinyDB('.data/twitter_api_db.json')

COVERS_PATH='.data/cover_images'
TESTING_USER='TestingIgnoreM1'

# Support keys from environment vars (Heroku / Glitch).
app.config['APP_CONSUMER_KEY'] = os.getenv(
    'APP_CONSUMER_KEY', 'API_Key_from_Spotify')
app.config['APP_CONSUMER_SECRET'] = os.getenv(
    'APP_CONSUMER_SECRET', 'API_Secret_from_Spotify')
app.config['SECRET_KEY'] = os.getenv(
    'APP_FLASK_SECRET', 'FLASK_SECRET')
app.config['TWITTER_APP_KEY'] = os.getenv(
    'TWITTER_APP_KEY', 'TWITTER APP KEY')
app.config['TWITTER_APP_SECRET'] = os.getenv(
    'TWITTER_APP_SECRET', 'TWITTER APP SECRET')
app.config['TWITTER_OAUTH_TOKEN'] = os.getenv(
    'TWITTER_OAUTH_TOKEN', 'TWITTER OAUTH TOKEN')
app.config['TWITTER_OAUTH_SECRET'] = os.getenv(
    'TWITTER_OAUTH_SECRET', 'TWITTER OAUTH SECRET')
app.config['TWITTER_POST_APP_KEY'] = os.getenv(
    'TWITTER_POST_APP_KEY', 'TWITTER POST APP KEY')
app.config['TWITTER_POST_APP_SECRET'] = os.getenv(
    'TWITTER_POST_APP_SECRET', 'TWITTER POST APP SECRET')
app.config['TWITTER_POST_OAUTH_TOKEN'] = os.getenv(
    'TWITTER_POST_OAUTH_TOKEN', 'TWITTER POST OAUTH TOKEN')
app.config['TWITTER_POST_OAUTH_SECRET'] = os.getenv(
    'TWITTER_POST_OAUTH_SECRET', 'TWITTER POST OAUTH SECRET')

#set up the Flask session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '.data/.flask_session/'
Session(app)

#set up logging
LOGGING_PATH = '.data/logs/'
if not os.path.exists(LOGGING_PATH):
    os.makedirs(LOGGING_PATH)
if not app.debug:
  logging.basicConfig(filename=(LOGGING_PATH+'web.log'), level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')
else:
  logging.basicConfig(filename=(LOGGING_PATH+'web.log'), level=logging.DEBUG, format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

#the scope for the spotify permissions
SCOPE = 'playlist-modify playlist-modify-public playlist-modify-private user-read-email ugc-image-upload'

@app.route('/')
def index():
  return('nothing to see here')

#brings a user through the process of linking their spotify ID to a twitter username
@app.route('/start', methods=['GET', 'POST'])
def start():
    #create a session if one doesn't exist
    if not session.get('uuid'):
        # Step 1. Visitor is unknown, give random ID
        session['uuid'] = str(uuid.uuid4())
        
    #begin setting up the spotipy / spotify credentials -- this happens on hitting the web page for the first time, which todo I should change
    cache_handler=misc_util.get_spotipy_cache_handler(username=session['uuid'])
    auth_manager=misc_util.get_spotipy_auth_manager(cache_handler=cache_handler, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('start', _external=True), scope=SCOPE)

    #if we are in the second step of the authorization flow then get an access token from spotify
    if request.args.get("code"):
        # Step 3. Being redirected from Spotify auth page
        auth_manager.get_access_token(request.args.get("code"))
        return redirect(url_for('start', _external=True))

    #if we are in the first step, check that we don't already have a token, if not then start the authorization process
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        # Step 2. Display sign in link when no token
        auth_url = auth_manager.get_authorize_url()
        return f'<h2>The first step is to <a href="{auth_url}">authorize spotify</a></h2>'

    # Step 4. Signed in with Spotify, get the twitter username
    #begin setting up the twitter credentials -- this happens on hitting the web page for the first time, which todo I should change
    auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'], url_for('start', _external=True))
    
    #if we are in the second step of the twitter authorization flow then get an access token
    #and write it all into the database
    if request.args.get("oauth_verifier") and 'twitter_oauth' in session:
        # Step 6. Being redirected from Twitter auth page
        auth.request_token = {'oauth_token' : session['twitter_oauth'],
                              'oauth_token_secret' : request.args.get("oauth_verifier") }
        try:
          auth.get_access_token(request.args.get("oauth_verifier"))
        except tweepy.TweepError:
          return ('Error! Failed to get access token.')
        auth2 = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'], url_for('start', _external=True))
        auth2.set_access_token(auth.access_token,auth.access_token_secret)
        twitter_api = tweepy.API(auth2)
        try:
          screen_name=twitter_api.verify_credentials().screen_name
        except tweepy.TweepError:
          return ('Error! Failed to verify auth.')
        #make a playlist for the user's timeline
        #copy the session_id to be the twitter_username session_id (the old one stays until the user signs out or we do garbage clean up)
        shutil.copy(misc_util.session_cache_path(username=session['uuid']), misc_util.session_cache_path(username=screen_name))

        #get a spotify for the user (and it MUST exist)
        sp=misc_util.get_spotify_for_user(user=screen_name, 
                                          logging=logging, 
                                          client_id=app.config['APP_CONSUMER_KEY'], 
                                          client_secret=app.config['APP_CONSUMER_SECRET'], 
                                          redirect_uri=url_for('start', _external=True), scope=SCOPE)
        playlist=misc_util.make_spotify_playlist_with_image(sp, sp.me()['id'],
                                                            'AttnFeedDJ: Twitter Timeline Playlist', 
                                                            misc_util.get_cover_image(COVERS_PATH), 
                                                            logging)
        #put the right stuff in the database
        query = Query()
        results= user_db.search(query.twitter_username == screen_name)
        if results:
          user_db.update({'access_token':auth.access_token, 'access_token_secret':auth.access_token_secret, 
                         'timeline_playlist_id':playlist['id'], 'spotify_email':sp.me()['email']}, 
                         query.twitter_username == screen_name)
        else:
          user_db.insert({'twitter_username':screen_name,'spotify_email':sp.me()['email'],
                          'access_token':auth.access_token, 'access_token_secret':auth.access_token_secret,
                          'timeline_playlist_id':playlist['id']})
        logging.info('Added Twitter authorization for @'+screen_name+' spotify '+sp.me()['email'])
        return('Success go tweet mentioning @AttnFeedDJ. This is your <a href="'+playlist['external_urls']['spotify']+'">timeline playlist</a>')

    #if we are in the first step of the twitter signin, check that we don't already have a token, if not then start the authorization process
    # Step 5. Display sign in link when no token
    try:
      redirect_url = auth.get_authorization_url()
      session['twitter_oauth']= auth.request_token['oauth_token']
      return redirect(redirect_url)
    except tweepy.TweepError as err:
      return ('Error! Failed to get request token.'+str(err))
    return 'You should not be here'

#this just removes the session id stuff
@app.route('/sign_out')
def sign_out():
    try:
        # Remove the CACHE file (.cache-test) so that a new user can authorize.
        os.remove(misc_util.session_cache_path(username=session['uuid']))
        session.clear()
    except OSError as e:
        print ("Error: %s - %s." % (e.filename, e.strerror))
        logging.warn("Error signing out: %s - %s." % (e.filename, e.strerror))
    return redirect('/')
  

#todo secure this so it is just from 127.0.0.1
#this checks for new @attnfeeddj mentions and generates playlists and entries in the playlist_searches_db if it finds any from users who are registered
@app.route('/check')
def check():
  logging.debug("Check mentions to add playlists started")
  #set up the Twitter auth
  auth = tweepy.OAuthHandler(app.config['TWITTER_POST_APP_KEY'], app.config['TWITTER_POST_APP_SECRET'])
  auth.set_access_token(app.config['TWITTER_POST_OAUTH_TOKEN'], app.config['TWITTER_POST_OAUTH_SECRET'])
  twitter_api = tweepy.API(auth)
  #do the call to twitter and return any tweets to process
  tweets_to_process=misc_util.check_mentions(twitter_db, twitter_api)
  result={'error':False, 'tweets_processed':[]}
  if not tweets_to_process: 
    logging.info("Check Mentions: No new tweets to process for new playlists")
    #return(str({'error':False, 'info':"No new tweets to process for new"}))
    return('OK')
  else:
    #for each tweet that is to be processed
    for tweet in tweets_to_process:
      #look up the user in the user_db to see if they exist
      logging.debug("CHECK PROCESSING: "+str(tweet))
      query = Query()
      results= user_db.search(query.twitter_username == tweet.user.screen_name)
      #if they don't exist
      if not results:
        logging.warn("Error User @"+tweet.user.screen_name+" not in the datbase")
        #todo respond on Twitter to the user
      else:
        #if we find a user, figure out what type of playlist to create for the user, create a playlist for the user, add the playlist to the playlist db, and reply to the user with a "good to go"
        sp=misc_util.get_spotify_for_user(user=tweet.user.screen_name, logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('start', _external=True), scope=SCOPE)
        user_id = sp.me()['id']
        #figure out what type of playlist to create
        #todo don't insert if I already have that playlist
        new_search = misc_util.get_hashtag(tweet)
        if new_search:
          #check to make sure we don't already have a playlist
          if playlist_searches_db.search(Query().search_terms == new_search):
            logging.info('ALREADY TRACKING PLAYLIST FOR: '+str(new_search))
          else:
            logging.debug("CHECK FOUND REQUEST FOR SEARCH: "+str(tweet))
            logging.debug("In search request")
            #create the playlist
            playlist=misc_util.make_spotify_playlist_with_image(sp, user_id, 'AttnFeedDJ: #'+str(new_search), misc_util.get_cover_image(COVERS_PATH), logging)
            #add it to the playlist_searches_db
            playlist_searches_db.insert({'twitter_username':tweet.user.screen_name, 'original_tweet_id':tweet.id, 'playlist_id':playlist['id'], 'search_terms':str(new_search)})
            #tweet the message to the user
            twitter_api.update_status('@'+tweet.user.screen_name+' You are all set up at '+playlist['external_urls']['spotify']+' I\'ll watch the hashtag #'+str(new_search)+' and add songs for tweets I find that also have one of the hashtags #AttnFeedDJ, #playlist or #DJ', tweet.id)
            result['tweets_processed'].append(tweet)
        else:
          logging.warn('ERROR: unknown playlist type:' + tweet.text)
    #todo later, distinguish between looking at replies, being tagged into a tweetstream, and hashtags
    #if we don't find the user, respond with an error
  #return(str(result))
  return('OK')

#this function looks through all the registered playlists and sees if there are songs to add
@app.route('/process_searches')
def process_searches():
  temp="<PRE>"
  logging.debug("Check for new tweets from searches to add as tracks started")
  #get a twitter api setup
  auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
  auth.set_access_token(app.config['TWITTER_OAUTH_TOKEN'], app.config['TWITTER_OAUTH_SECRET'])
  twitter_api = tweepy.API(auth)
  auth = tweepy.OAuthHandler(app.config['TWITTER_POST_APP_KEY'], app.config['TWITTER_POST_APP_SECRET'])
  auth.set_access_token(app.config['TWITTER_POST_OAUTH_TOKEN'], app.config['TWITTER_POST_OAUTH_SECRET'])
  twitter_post_api = tweepy.API(auth)
  #go through the playlist_searches_db looking for searches to do for tweets
  searches = misc_util.get_playlist_searches(playlist_searches_db)
  if searches:
    #format the appropriate search
    for search in searches:
      tweets_to_process = misc_util.check_hashtag(twitter_db, twitter_api, search['search_terms'], search['original_tweet_id'], logging)
      #grab an sp for the user if there are tweets to process
      if tweets_to_process:
        sp=misc_util.get_spotify_for_user(user=search['twitter_username'], logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('start', _external=True), scope=SCOPE)  
      for tweet in tweets_to_process:
        if sp:
          #don't try to find songs in explanations from the user
          if not (search['twitter_username'].lower() == tweet.user.screen_name.lower() and misc_util.is_search_explanation(tweet)):
            #find a song in the tweet
            track=misc_util.find_song(tweet, sp, logging, twitter_post_api)
            if track:
              #if found a song, add it to the right playlist
              temp=temp+misc_util.add_track_to_playlist(track, sp, search['playlist_id'], logging)+'<br /'
            else:
              temp=temp+"Couldn't find a song for "+tweet.text+'<br />'
          else:
            temp=temp+"Tweet is an explanation tweet "+tweet.text+'<br />'
        else:
          temp=temp+"Couldn't get a token for user"+user+'<br />'
    temp=temp+'<br />'     
  else:
   return("No searches to perform")
  #return(temp)
  return('OK')

#this function doesn't work as it will only get the timeline for attnfeeddj
@app.route('/process_timelines')
def process_timelines():
  temp="<PRE>"
  logging.debug("TIMELINES: Check for timelines started")
  #start twitter api setup
  auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
  #go through the playlist_searches_db looking for searches to do for tweets
  users = misc_util.get_users_for_timelines(user_db)
  for user in users:
    temp=temp+str(user)+'<br />'
    #finish the twitter setup for the user
    auth.set_access_token(user['access_token'],user['access_token_secret'])
    twitter_api = tweepy.API(auth)

    #grab an sp for the user
    sp=misc_util.get_spotify_for_user(user=user['twitter_username'], logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('start', _external=True), scope=SCOPE)
    tweets_to_process = misc_util.check_timeline(twitter_db, twitter_api, user['twitter_username'], logging)  
    for tweet in tweets_to_process:
      logging.info("Processing Tweet from Timeline: https://twitter.com/"+tweet.user.screen_name+'/status/'+str(tweet.id))
      track=misc_util.find_song(tweet = tweet, sp=sp, logging=logging, twitter_api=twitter_api, check_links=True, check_text=False, tweet_for_rickroll=False)
      if track:
        #if found a song, add it to the right playlist
        temp=temp+misc_util.add_track_to_playlist(track, sp, user['timeline_playlist_id'], logging)+'<br /'
      else:
        temp=temp+"Couldn't find a song for "+tweet.text+'<br />'  
    temp=temp+'<br />'     
  #return(temp)
  return('OK')
  
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_message='uncaught exception'), 500
 
if __name__ == '__main__':
  app.config['TEMPLATES_AUTO_RELOAD'] = True
  app.run()
