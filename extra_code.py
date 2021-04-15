#this function is only for development. Returns a song lookup for a tweetid
@app.route('/song')
def song_lookup():
  # and type(request.args.get('id')) == int
  if request.args.get('id'):
    try:
      id = int(request.args.get('id'))
    except:
      return("Error")
    #lookup the tweetid
    auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
    auth.set_access_token(app.config['TWITTER_OAUTH_TOKEN'], app.config['TWITTER_OAUTH_SECRET'])
    twitter_api = tweepy.API(auth)
    tweet= twitter_api.get_status(id, include_entities=True, include_card_uri=True, include_ext_alt_text=True)
    if tweet:
      sp=misc_util.get_spotify_for_user(user=TESTING_USER, logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('start', _external=True), scope=SCOPE)  
      if not sp:
        return("Error creating spotify")
      track=misc_util.find_song(tweet, sp, logging, twitter_api)
      if track:
        return(str(track))
      else:
        return("Error: couldn't find song for tweet -- "+str(tweet.text))
    else:
      return("Error: couldn't find tweet")
  else: 
    return("invalid request")

#this function is only for development. Returns JSON of Tweet
@app.route('/tweet')
def tweet_lookup():
  # and type(request.args.get('id')) == int
  if request.args.get('id'):
    try:
      id = int(request.args.get('id'))
    except:
      return("Error")
    #lookup the tweetid
    auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
    auth.set_access_token(app.config['TWITTER_OAUTH_TOKEN'], app.config['TWITTER_OAUTH_SECRET'])
    twitter_api = tweepy.API(auth)
    tweet= twitter_api.get_status(id, include_entities=True, include_card_uri=True, include_ext_alt_text=True)
    return(str(tweet._json))
  else: 
    return("invalid request")

#this function is only for development. Returns a song lookup for a tweetid
@app.route('/song')
def song_lookup():
  # and type(request.args.get('id')) == int
  if request.args.get('id'):
    try:
      id = int(request.args.get('id'))
    except:
      return("Error")
    #lookup the tweetid
    auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
    auth.set_access_token(app.config['TWITTER_OAUTH_TOKEN'], app.config['TWITTER_OAUTH_SECRET'])
    twitter_api = tweepy.API(auth)
    tweet= twitter_api.get_status(id, include_entities=True, include_card_uri=True, include_ext_alt_text=True)
    if tweet:
      sp=misc_util.get_spotify_for_user(user=TESTING_USER, logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('signup', _external=True), scope=SCOPE)  
      if not sp:
        return("Error creating spotify")
      track=misc_util.find_song(tweet, sp, logging, twitter_api)
      if track:
        return(str(track))
      else:
        return("Error: couldn't find song for tweet -- "+str(tweet.text))
    else:
      return("Error: couldn't find tweet")
  else: 
    return("invalid request")


#from check
        if misc_util.is_request_for_reply_playlist(tweet):
          playlist=misc_util.make_spotify_playlist_with_image(sp, user_id, 'AttnFeedDJ: '+misc_util.sanitize_tweet_text(tweet.text), misc_util.get_cover_image(COVERS_PATH), logging)
          playlist_replies_db.insert({'twitter_username':tweet.user.screen_name, 'original_tweet_id':tweet.id, 'playlist_id':playlist['id']})
          twitter_api.update_status('@'+tweet.user.screen_name+' You are all set up at '+playlist['external_urls']['spotify']+' I\'ll watch the replies and add the songs I find', tweet.id)
          result['tweets_processed'].append(tweet)  

#this function looks through all the registered playlists and sees if there are songs to add
@app.route('/process_replies')
def process_replies():
  logging.debug("Check for new replies to add as tracks started")
  #get a twitter api setup
  auth = tweepy.OAuthHandler(app.config['TWITTER_APP_KEY'], app.config['TWITTER_APP_SECRET'])
  auth.set_access_token(app.config['TWITTER_OAUTH_TOKEN'], app.config['TWITTER_OAUTH_SECRET'])
  twitter_api = tweepy.API(auth)
  #go through the playlist_replies_db looking for tweets to check by user
  temp='<PRE>'
  #users is an array of twitter usernames
  users=misc_util.users_in_playlist_replies_db(playlist_replies_db)
  for user in users:
    #user_playlists is an array of the original tweet ids that are associated with a specific user for a specific playlist
    user_playlists = misc_util.playlist_replies_for_user(playlist_replies_db, user)
    logging.debug('PROCESS REPLIES: in user '+user+' playlist_ids are '+str(user_playlists))
    #we get an array of tweets that are mentions of the user that are replies to that set of tweets
    tweets_to_process= misc_util.check_replies(twitter_db, twitter_api, user, user_playlists, logging)
    if not tweets_to_process:
      logging.debug('PROCESS_REPLIES: No new tweets for user '+user+' playlist_ids are '+str(user_playlists))
      temp=temp+"No new tweets for "+user
    else:
      #playlist_ids is a hash for looking up (by tweet_id) playlists
      playlist_ids=misc_util.playlist_replies_lookup_by_tweet_id(playlist_replies_db,user_playlists)
      #go through each tweet to see if we can find a song
      for tweet in tweets_to_process:
        #first try to find urls to specific tracks
        #grab an sp for the user
        sp=misc_util.get_spotify_for_user(user=user, logging=logging, client_id=app.config['APP_CONSUMER_KEY'], client_secret=app.config['APP_CONSUMER_SECRET'], redirect_uri=url_for('signup', _external=True), scope=SCOPE)
        if sp:
          #find a song in the tweet
          track=misc_util.find_song(tweet, sp, logging, twitter_api)
          if track:
            #if found a song, add it to the right playlist
            temp=temp+misc_util.add_track_to_playlist(track, sp, playlist_ids[str(tweet.in_reply_to_status_id)], logging)+'<br /'
          else:
            temp=temp+"Couldn't find a song for "+tweet.text+'<br />'  
        else:
          temp=temp+"Couldn't get a token for user"+user+'<br />'
    temp=temp+'<br />'
    #todo later, distinguish between looking at replies, being tagged into a tweetstream, and hashtags
    #if we don't find the user, respond with an error
  #return(temp)
  return('OK')