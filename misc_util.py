import tweepy
import spotipy
import urllib
import requests
from tinydb import TinyDB, Query
import re
import os
import random
import base64
from uuid import UUID
SEARCH_KEYWORDS=['attnfeeddj', 'dj', 'playlist']

#checks if a thing is a valid uuid (returns True if it is False if not)
def is_valid_uuid(input):
  try:
    uuid_obj = UUID(input)
    return True
  except ValueError:
    return False
  
#set up the spotipy caches which start as being Flask Sessions UUID and then get copied over to ./data/.spotify_caches_twitter_[twitter_username]
def session_cache_path(username):
  caches_folder = '.data/.spotify_caches/'
  if not os.path.exists(caches_folder):
    os.makedirs(caches_folder)
  if is_valid_uuid(username):
    return caches_folder + str(username)
  else:
    return caches_folder + 'twitter_' + username

def is_valid_new_user(db, twitter_username, spotify_email):
  query = Query()
  results = db.search(query.twitter_username == twitter_username)
  if results:
    return False
  query = Query()
  results = db.search(query.spotify_email == spotify_email)
  if results:
    return False
  return True

def get_cover_image(covers_path):
  cover_file=covers_path+'/'+random.choice(os.listdir(covers_path))
  str=''
  if cover_file:
    with open(cover_file, "rb") as imageFile:
      str = base64.b64encode(imageFile.read())
  return(str)

def get_spotipy_cache_handler(username):
  return spotipy.cache_handler.CacheFileHandler(session_cache_path(username=username))

def get_spotipy_auth_manager(cache_handler, client_id, client_secret, redirect_uri, scope):
  auth_manager = spotipy.oauth2.SpotifyOAuth(client_id=client_id, client_secret=client_secret,redirect_uri=redirect_uri,scope=scope,cache_handler=cache_handler,show_dialog=True)
  return(auth_manager)

def make_spotify_playlist_with_image(sp, user_id, playlist_name, cover_image, logging):
  playlist=False
  playlist=sp.user_playlist_create(user_id, playlist_name)
  if playlist and cover_image:
    logging.debug('COVER IMAGE UPLOAD: '+playlist['id'])
    sp.playlist_upload_cover_image(playlist['id'], cover_image)
  return(playlist)
  
def last_tweet_id(db, query_type):
	query = Query()
	results= db.search(query.type == query_type)
	if results:
		return(results[0]['tweet_id'])
	else:
		#create the record, with a value of 1
		db.insert({'type':query_type, 'tweet_id':1})
		return(1)

def update_last_tweet_id(db, query_type, new_since_id):
	query = Query()
	return(db.update({'tweet_id': new_since_id}, query.type == query_type))

def get_playlist_searches(playlist_searches_db):
  results=playlist_searches_db.all()
  return(results)

def get_users_for_timelines(user_db):
  results=user_db.all()
  return(results)

def sanitize_tweet_text(tweet_text):
  #get rid of usernames & hashtags
  result = re.sub(r'[\@\#][a-zA-Z_0-9]+', ' ',   tweet_text)  
  result = re.sub(r'\/cc', ' ',   result)  
  #get rid of t.co links
  result = re.sub(r'https\:\/\/t.co\/[a-zA-Z0-9_]+', ' ',   result)  
  #get rid of extra spaces
  result = re.sub(r' +', ' ',   result)  
  result = re.sub(r'^\s+', '',   result)  
  result = re.sub(r'\s+$', '',   result)  
  #todo deal with '-' at beginning of words and other search modifiers (and etc.)
  return(result)

def sanitize_title(title_text):
  #specially process YouTube titles which have the form Artist - Song - YouTube
  #can also be artist song - YouTube todo figure out which is which
  if re.search(r'YouTube', title_text):
    (artist, song, yt) = title_text.split(' - ')
    title_text=song+' '+artist
  result = re.sub(r'YouTube', ' ',   title_text)
  result = re.sub(r'on\sApple\sMusic', ' ',   result)
  result = re.sub(r' \&amp;', ' and ',   result)  
  result = re.sub(r'\-', ' ',   result)
  result=sanitize_tweet_text(result)
  #todo deal with '-' at beginning of words and other search modifiers (and etc.)
  return(result)

#check to see if this is someone explaining how to tweet a song
#we are checking to see if ALL the search keywords are in the tweet
def is_search_explanation(tweet):
  if tweet.entities is not None and 'hashtags' in tweet.entities:
    terms={}
    for item in SEARCH_KEYWORDS:
      terms[str(item).lower()]=False
    for hashtag in tweet.entities['hashtags']:
      if (hashtag['text'].lower() in SEARCH_KEYWORDS):
        terms[hashtag['text'].lower()]=True
    for item in SEARCH_KEYWORDS:
      if not terms[str(item).lower()]:
        return(False)
    return(True)
  else:
    return(False)

#for a tweet, see if there is exactly 1 hashtag that is not in the SEARCH_KEYWORDS list
#if so, we have a request for a search playlist. Return that term.
def get_hashtag(tweet):
  terms=[]
  if tweet.entities is not None and 'hashtags' in tweet.entities:
    for hashtag in tweet.entities['hashtags']:
      if not (hashtag['text'].lower() in SEARCH_KEYWORDS):
        terms.append(hashtag['text'])
  if len(terms)==1:
    return(terms[0])
  else:
    return(False)

#return the sp and log any errors
def get_spotify_for_user(user, client_id, client_secret, redirect_uri, scope, logging):
  sp=False
  cache_handler=get_spotipy_cache_handler(user)
  auth_manager=get_spotipy_auth_manager(cache_handler=cache_handler, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri, scope=scope)
  try:
    sp = spotipy.Spotify(auth_manager=auth_manager)
  except spotipy.exceptions.SpotifyException as err:
    logging.warn('Could not get Spotify Token for user: '+user+ ' ' + str(err))
  return(sp)

#given two strings return the number of words they share
def similarity_score(s1, s2):
  s1 = s1.lower().split(' ')
  s2 = s2.lower().split(' ')
  return len(list(set(s1)&set(s2)))
  
#given a track_id and a playlist_id add the track to the playlist
#return any messages
def add_track_to_playlist(track, sp, playlist_id, logging):
  temp=""
  try:
    #get the track
    logging.debug("Track in Track_to_playlist:" +str(track))
    sp.playlist_add_items(playlist_id, [track['id']])
    logging.debug('Added: '+track['name']+' to: '+str(playlist_id))
    temp=temp+'Added: '+track['name']+'<br />'
  except spotipy.exceptions.SpotifyException as err:
    logging.warn("Spotify Error adding track "+track['id']+' to playlist '+str(playlist_id)+str(err))
    temp=temp+"Spotify Error adding track "+track['uri']+' to playlist '+str(playlist_id)+str(err)+'<br />'
  return(temp)

def search_spotify(sp, logging, terms):
  result_track=False
  if terms == '':
    return(result_track)
  try:
    result = sp.search(terms, type='track', limit=10)
    #if no results, try again without the "by"
    if (not (result and 'tracks' in result and 'items' in result['tracks'] and len(result['tracks']['items'])>0)) and re.search(r' by ', terms, re.IGNORECASE):
      result = sp.search(re.sub(r' by ', ' ',   terms, re.IGNORECASE), type='track', limit=10)
      logging.warn("Tried removing the by in "+terms)
  except spotipy.exceptions.SpotifyException as err:
    logging.warn("Spotify Error searching "+terms+' '+str(err))
  if result and 'tracks' in result and 'items' in result['tracks'] and len(result['tracks']['items'])>0:
    song_best=-1
    album_best=-1
    artist_best=-1
    most_popular=-1
    for track in result['tracks']['items']:
      song_score=similarity_score(track['name'],terms)
      album_score=similarity_score(track['album']['name'],terms)
      artist_string=''
      for artist in track['artists']:
        artist_string = ' '.join([artist_string, artist['name']])
      artist_score=similarity_score(artist_string,terms)
      if song_score>song_best:
        song_best=song_score
        artist_best=artist_score
        most_popular=track['popularity']
        result_track=track
      elif song_score==song_best and album_score>album_best:
        album_best=album_score
        artist_best=artist_score
        most_popular=track['popularity']
        result_track=track
      elif song_score==song_best and album_score==album_best and artist_score>artist_best:
        artist_best=artist_score
        most_popular=track['popularity']
        result_track=track
      elif song_score==song_best and album_score==album_best and artist_score==artist_best and track['popularity']>most_popular:
        #compare popularity
        most_popular=most_popular=track['popularity']
        result_track=track
      logging.debug('Found Track: '+str(song_score)+'.'+str(album_score)+'.'+str(artist_score)+'.'+str(track['popularity'])+' '+track['name']+' - '+track['album']['name']+' - '+artist_string)
    logging.debug('Chose Track:'+result_track['name'])
  else:
    logging.warn('Did not find a song for terms: '+terms)
  return(result_track)

#should return a track or False
def find_song(tweet, sp, logging, twitter_api, check_links=True, check_text=True, tweet_for_rickroll=True):
  #first try to find urls to specific tracks
  track=False
  found_url=False
  if check_links and tweet.entities is not None and 'urls' in tweet.entities:
          for url in tweet.entities['urls']:
            if 'expanded_url' in url:
              #todo, deal with podcast episodes (see https://open.spotify.com/episode/6DKW7UciB4RVoM53zxEYCc)
              pattern = re.compile("^https://open.spotify.com/track/[a-zA-Z0-9]{22,22}")
              matched=pattern.match(url['expanded_url'])
              if matched:
                #check to see if the track exists on spotify
                urn = 'spotify:track:'+url['expanded_url'][31:53]
                #add in stuff to handle being rickrolled https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC
                try:
                  track =  sp.track(urn)
                  found_url=True
                except spotipy.exceptions.SpotifyException as err:
                  logging.warn('Could not find track from: URL '+url['expanded_url'])
              else:
                #we don't have a spotify link, grab the title of the page and see whether that can be looked up
                page = requests.get(url['expanded_url'])
                if page and hasattr(page,'text'):
                  title = re.search(r'(?<=<title>)(.+?)(?=</title>)', page.text, (re.DOTALL | re.IGNORECASE))
                  if title and title.group(1):
                    terms = str(sanitize_title(str(title.group(1))))
                    track = search_spotify(sp, logging, terms)
                    if track:
                      logging.info('Found: '+str(track['name'])+' from url '+url['expanded_url']+' with terms'+terms)
                      found_url=True
                    else:
                        logging.warn('Did not find a song for URL: '+url['expanded_url'])
  #if I haven't found a url that was added, try searching on a sanitized version of the tweet text
  if check_text and not found_url:
          terms=sanitize_tweet_text(tweet.text)
          #do a search
          track = search_spotify(sp, logging, terms)
          if track:
            logging.debug('Found: '+str(track['name'])+' from text '+tweet.text)
          else:
            logging.warn('Did not find a song for: '+tweet.text)
  #don't get rickrolled
  if track and track['name'].lower() == "never gonna give you up":
    logging.info("Someone tried Never Gonna Give You Up: "+str(track))
    track = False
    if tweet_for_rickroll:
      twitter_api.update_status('@'+tweet.user.screen_name+' nice try.', tweet.id)
  logging.debug("Track in find song: "+str(track))
  return(track)

def check_mentions(db, twitter_api):
  keywords=['attnfeeddj']
  results = []
  since_id = last_tweet_id(db, "signups")
  new_since_id=since_id
  for tweet in tweepy.Cursor(twitter_api.mentions_timeline,since_id=since_id).items():
    new_since_id = max(tweet.id, new_since_id)
    #update the db with the new since_id
    update_last_tweet_id(db, 'signups', new_since_id)
    if tweet.in_reply_to_status_id is not None:
      continue
    if '#attnfeeddj' in tweet.text.lower():
      continue
    if any(keyword in tweet.text.lower() for keyword in keywords):
      results.append(tweet)
  return(results)

def check_replies(twitter_db, twitter_api, twitter_username, tweet_ids, logging):
  since_id = max(last_tweet_id(twitter_db, twitter_username), min(tweet_ids))
  new_since_id=since_id
  results=[]
  logging.debug("CHECK REPLIES: "+twitter_username+' '+str(new_since_id))
  for tweet in tweepy.Cursor(twitter_api.search,q='to:'+twitter_username, result_type='recent', since_id=since_id).items():
    logging.debug("CHECK REPLIES FOUND TWEETS: "+twitter_username+' '+str(new_since_id) + ' '+str(tweet))
    new_since_id = max(tweet.id, new_since_id)
    #update the db with the new since_id
    update_last_tweet_id(twitter_db, twitter_username, new_since_id)
    #ignore tweets that are not replies
    if tweet.in_reply_to_status_id is None:
      continue
    #ignore tweets that are from attnfeedj
    if tweet.user.screen_name.lower() == 'attnfeeddj':
      continue
    if tweet.in_reply_to_status_id in tweet_ids:
      results.append(tweet)
  return(results)

def check_hashtag(twitter_db, twitter_api, hashtag, tweet_id, logging):
  since_id = max(last_tweet_id(twitter_db, 'hashtag_'+hashtag),tweet_id)
  new_since_id=since_id
  results=[]
  query='#'+str(hashtag)+' (#'+ (' OR #').join(SEARCH_KEYWORDS)+')'
  logging.debug("CHECK HASHTAG: "+hashtag+' '+str(new_since_id)+' QUERY = '+query)
  for tweet in tweepy.Cursor(twitter_api.search,q=query, result_type='recent', since_id=since_id).items():
    logging.debug("CHECK HASHTAG FOUND TWEETS"+str(tweet))
    new_since_id = max(tweet.id, new_since_id)
    #update the db with the new since_id
    update_last_tweet_id(twitter_db, 'hashtag_'+hashtag, new_since_id)
    #ignore tweets that are from attnfeedj
    if tweet.user.screen_name.lower() == 'attnfeeddj':
      continue
    results.append(tweet)
  return(results)

#todo deal with retweets and links to tweets?
def check_timeline(twitter_db, twitter_api, twitter_username, logging):
  results=[]
  since_id = last_tweet_id(twitter_db, 'timeline_'+twitter_username)
  #we don't want to grab a ton of tweets for timelines, so this will be triggered the first time
  if since_id==1:
    since_id=last_tweet_id(twitter_db,'signups')
  new_since_id=since_id
  logging.info("CHECK TIMELINE: "+twitter_username+' '+str(new_since_id))
  for tweet in tweepy.Cursor(twitter_api.home_timeline,screen_name=twitter_username,since_id=since_id).items():
    logging.info("CHECK TIMELINE FOUND TWEETS"+'-'+str(tweet.id))
    new_since_id = max(tweet.id, new_since_id)
    update_last_tweet_id(twitter_db, 'timeline_'+twitter_username, new_since_id)
    #ignore tweets that are from attnfeedj
    if tweet.user.screen_name.lower() == 'attnfeeddj':
      continue
    if tweet.user.screen_name.lower() == twitter_username.lower():
      continue
    results.append(tweet)
    #update the db with the new since_id
  return(results)

#given a playlist_db, create a list of users and their list of original_tweet_ids and playlists
def users_in_playlist_replies_db(playlist_replies_db):
  users=[]
  for playlist in playlist_replies_db.all():
    if playlist['twitter_username'] not in users:
      users.append(playlist['twitter_username'])
  return(users)

#redo this
def playlist_replies_for_user(playlist_replies_db, twitter_username):
  playlists=[]
  playlist = Query()
  for playlist in playlist_replies_db.search(playlist.twitter_username == twitter_username):
    playlists.append(playlist['original_tweet_id'])  
  return(playlists)

def playlist_replies_lookup_by_tweet_id(playlist_replies_db,user_playlists_tweets):
  playlist_ids={}
  for tweet_id in user_playlists_tweets:
    playlist = Query()
    for playlist in playlist_replies_db.search(playlist.original_tweet_id == tweet_id):
      playlist_ids[str(playlist['original_tweet_id'])]=playlist['playlist_id']
  return(playlist_ids)