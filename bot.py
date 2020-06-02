from instagram_private_api import Client, ClientCompatPatch
from dotenv import load_dotenv, find_dotenv
import json
import urllib.request
import os
import time
import ssl
import logging
import numpy as np
import urllib
import cv2
import traceback
from ratelimiter import RateLimiter
ssl._create_default_https_context = ssl._create_unverified_context




def main():
	bot = BLMBot()
	bot.start()


class BLMBot():

	logger = None
	cache = None
	account_creds = []
	client_objs = []
	rate_limiter = None
	MESSAGE = "Hi, please don't use the blacklivesmatter tag as it is currently blocking important info from being shared. Please delete and repost with #BlackoutTuesday instead (Editing the caption wont work). If you want other ways to help please check out our bio. Thank you :)"



	def __init__(self,accountlist="accountlist.txt"):
		# Set up logging
		logging.basicConfig(level=logging.INFO,
						format='%(asctime)s.%(msecs)03d %(name)-12s %(levelname)-8s %(message)s',
						datefmt='%m-%d-%y %H:%M:%S',
		)
		self.rate_limiter = RateLimiter(max_calls=1, period=5.0)
		self.logger = logging.getLogger("blmbot")

		self.log_info("Setting up bot")
		self.setupCredentials(accountlist)
		self.setupClients()
		self.setupFeedsByBLMTag()
		self.log_info("Bot successfully initialized")


	def setupCredentials(self,accountlist):
		self.log_info("Parsing credentials")
		# Set up Credentials
		try:
			with open(accountlist,"r") as f:
				accountlist_str = f.read()
				for line in accountlist_str.split("\n"):
					account_str = line.split("\t")
					username = account_str[0]
					password = account_str[1]
					self.account_creds.append({"u":username,"p":password})
		except Exception as e:
			self.log_critical("FAILURE TO READ ACCOUNT LIST FILE %s - SEE ERROR FOR MORE INFORMATION" % accountlist)
			self.log_error("%s\n%s" % (e,traceback.format_exc()))


	def setupClients(self):
		self.log_info("Setting up clients with given credentials")
		for account in self.account_creds:
			u = account["u"]
			p = account["p"]
			
			self.log_debug("Creating Instagram client object with username: %s " % u)
			
			try:
				c = Client(account["u"], account["p"])
				self.client_objs.append({"client":c,"feed":None,"u":u,"uuid":c.generate_uuid()})
				self.log_info("Successfully created Instagram client object with username: %s " % u)
			except Exception as e:
				self.log_warning("Error encountered when authenticating to Instagram with username: %s - SKIPPING" % u)
				self.log_error("%s\n%s" % (e,traceback.format_exc()))
				continue

	def setupFeedsByBLMTag(self):
		self.log_info("Setting up BLM tag feed with given clients")
		for client_obj in self.client_objs:
			try:
				client_obj["feed"] = client_obj["client"].feed_tag("blacklivesmatter", client_obj["uuid"])
			except Exception as e:
				self.log_warning("Error encountered when creating feed for client: %s" % client_obj["u"])
				self.log_error("%s\n%s" % (e,traceback.format_exc()))
				continue

	def setupCache(self):
		self.log_info("Setting up cache")
		"""todo"""

	def start(self):
		self.log_info("Starting bot")
		self.handleFeed(client_objs[0])

	def handleFeed(self, client_obj):
		c = client_obj["client"]
		f = client_obj["feed"]
		u = client_obj["u"]
		uuid = client_obj["uuid"]
		self.log_info("Handling feed for user %s:" % u)
		feedValid = True
		while feedValid:
			if  f["num_results"] == 0:
				feedValid = False
				continue

			for post in f["items"]:
				self.handlePost(c, post)


			if f["more_available"]:
				self.log_info("REFRESHING FEED")
				client_obj["feed"] = c.feed_tag("blacklivesmatter",uuid,max_id=f["next_max_id"])
			else:
				feedValid = False

			# feedValid = False

	def handlePost(self, c, post):
		self.log_info("Handling post for id %s and url https://www.instagram.com/p/%s" % (post["id"],post["code"]))
		greenForComment = False
		if self.validateMeta(post) and self.validateImage(post):
			self.log_info("Approved for commenting on post %s!" % post["id"])
			greenForComment = True

		if greenForComment:
			try:
				with self.rate_limiter:
					c.post_comment(post['id'], self.MESSAGE)
					c.save_photo(post['id'])
			except Exception as e:
				self.log_warning("Error encountered when commenting/saving post: %s" % post["id"])
				self.log_error("%s\n%s" % (e,traceback.format_exc()))
			


	def validateMeta(self, post):
		self.log_info("Validating metadata for post %s" % (post["id"]))
		green = True
		if "preview_comments" in post:
			for comment in post['preview_comments']:
				if "use the blacklivesmatter tag" in comment['text'].lower():
					green = False
					break
		return green

	def validateImage(self, post):
		if "image_versions2" not in post:
			return False

		postUrl = post['image_versions2']['candidates'][1]['url']

		self.log_info("Validating image with URL %s" % postUrl)
		
		green = False
		resp = urllib.request.urlopen(postUrl)
		image = np.asarray(bytearray(resp.read()), dtype="uint8")
		image = cv2.imdecode(image, cv2.IMREAD_GRAYSCALE)
		n_black_pix = np.sum(image < 30)

		cv2.imshow('Debug', image)
		cv2.waitKey(1)

		if (float(n_black_pix) / float(image.size)) > 0.60:
			green = True

		return green


	def log_critical(self, message):
		self.logger.critical(message)

	def log_error(self, message):
		self.logger.error(message)

	def log_warning(self, message):
		self.logger.warning(message)

	def log_info(self, message):
		self.logger.info(message)

	def log_debug(self, message):
		self.logger.debug(message)


main()