#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Copyright (c) 2012 Douglas Hipolito do Nascimento

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import sys                
import os
import string
import shutil
import re
import getopt
from string import Template
import platform
import inspect

if platform.system().lower() != "windows" :
	import pwd
	from pwd import getpwnam

class ManageHosts :
	"""###Manage Hosts####
This application facilitates the creation of hosts through a few simple steps.
	"""

	__platform = ""
	confFile = '_managehosts.conf'
	domain = ""
	pathDomain = ""

	defaultssystem = { "windows" : {}, "macos" : {}, "linux" : {} }
	baseConfigs = {
		"hosts" 	 	 : "",
		"vhosts" 	 	 : "",
		"ipdomain"	 	 : "",
		"domainport" 	 : "",
		"basepathdomain" : "",
		"apacherestart"	 : "",
		"htdocs"		 : ""  
	}
	
	conf = { "windows" : baseConfigs, "macos" : baseConfigs, "linux" : baseConfigs }
	envir = {}

	initMarkupVhosts = ""
	endMarkupVhosts = ""
	originalUser = {}

	currentPathScript = ""

	asRoot = False

	def __init__(self) :
		self.__platform = "macos" if platform.system().lower() == "darwin" else platform.system().lower()
		self.__setDefaultsSystem()
		self.currentPathScript = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

		self.confFile = self.currentPathScript + os.sep + self.confFile

		if self.__platform != "windows" :
			if os.getenv("SUDO_USER") :
				self.originalUser = getpwnam(os.getenv("SUDO_USER"))
			else :
				self.originalUser = pwd.getpwuid(os.getuid())

			#Set sudo	
			euid = os.geteuid()
			if euid != 0:
			    args = ['sudo', sys.executable] + sys.argv + [os.environ]
			    print "* You must be root to change the hosts file, enter the password of root if prompted\n"		
			    os.execlpe('sudo', *args)

		if not os.path.isfile(self.confFile) :	
   			print "Configuration file doesn't exists, create now."
   			self.createConfiguration()

   		#Start configs	
		confs = open(self.confFile, 'r')
		dictConfig = { 'windows' : {}, 'macos' : {}, 'linux' : {} }
		for conf in confs : 
			if ("conf") in conf :
				m = re.match('conf\.([a-z]+)\.([a-z]+) ?= ?"(.*)"', conf.strip())
				dictConfig[m.group(1)][m.group(2)] = m.group(3)
				
		confs.close()

		#Update configs
		self.conf.update(dictConfig)
		
		#Set environment
		self.envir = self.conf[self.__platform]

		#Verify if exists configs for this OS
		if not self.envir:
			print "You don't have a configuration for your system! Add to file configuration."
			exit(1)

		#Set Separator for system	
		self.envir['pathseparator'] = os.sep

		#Makups for virtualhost
		self.initMarkupVhosts = '<VirtualHost *:80>'
		self.endMarkupVhosts = '</VirtualHost>'	
		
	def start(self) :
		self.selectOption()

	def selectOption(self, action = "init", args = "") :
		while True :
			action = action.replace("-", "")
			if action == "c" :
				self.setDomain(False, args)
				self.create()
				break
			elif action == "r" :
				if self.setDomain(True, args) :
					self.remove()
				break
			elif action == "l" :
				self.listDomains()
				break	
			elif action == "init" :
				action = raw_input("Create or Remove host (c/r)[!Q to exit] ? : ") . lower()
			elif action == "!q" :
				self.__VerifyRequestExit(action)
			else :
				action = raw_input("Option doesn't exists! Please, type C for Create or R for Remove (c/r) : ") . lower()

	def setDomain(self, remove = False, args = "") :
		domains = []
		if remove :
			self.domain = args or raw_input("Enter the domain or enter 'L to list all domains or !Q to exit : ") . lower()
			if self.domain == "l" :	
				domains = self.listDomains()
   				self.domain = raw_input("Choose a domain with at the above options : ")
				
				#if domain is !Q then exit
				self.__VerifyRequestExit(self.domain)	
				
				while True: 
					try :
						self.domain = domains[int(self.domain)]
						break
					except ValueError:
						self.domain = raw_input("Option domain doesn't exists! Please, Enter the domain by number or !Q to exit : ")
						
						#if domain is !Q then exit
						self.__VerifyRequestExit(self.domain)	
		else :
			self.domain = args or raw_input("Domain: ")
			self.pathDomain = self.envir["basepathdomain"] + '/' + self.domain

			vHostsFileExists = open(self.envir["vhosts"], 'r')
			
			for vhost in vHostsFileExists :
				if 'ServerName {0}' . format(self.domain) in vhost :
					print "Domain already created!"
					raw_input("Press any key to quit..")
					vHostsFileExists.close()
					exit(1)

			vHostsFileExists.close()		

			pathDomain = raw_input("Set PATH({0}) : " . format(self.pathDomain))
			self.pathDomain = pathDomain.replace("$BASEPATH", self.envir["basepathdomain"]) if pathDomain else self.pathDomain

		#if domain is !Q then exit
		self.__VerifyRequestExit(self.domain)			
		return True	

	def listDomains(self) :
		domains = self.listHosts()
		if not domains :
			action = raw_input("No domains to remove! You want to create a domain (Y/n) ? : ") . lower()
			if action == "y" or action == "" :
				self.selectOption("c")
			else :
				self.__VerifyRequestExit(action)
			return False

		for i, domainOption in enumerate(domains):
			print " [{0}] - {1} \n" . format(i, domainOption)

		return domains	
		
	def create(self) :	
		if not os.path.isdir(self.pathDomain) : 
			createDir = raw_input("Dir ('" + self.pathDomain + "') doesn't exists.. create now (Y/n) ? : ").lower()
			if createDir == "y" or createDir == "" : 
				os.makedirs(self.pathDomain, 0755)
				
				if self.__platform != "windows" :
					os.chown(self.pathDomain, self.originalUser[2], self.originalUser[3])
				
			elif createDir == "n" : 
				print "please, create dir later!"		

		withAlias = raw_input("Alias(www) : ")
		alias = "www." + self.domain

		if len(withAlias) > 0 :
			alias = withAlias

		vhostsConfig = '''
{0}
\tServerAdmin webmaster@{2}
\tDocumentRoot "{3}"
\tServerName {2}
\tServerAlias {4}
\tErrorLog "logs/{2}-error_log"
\tCustomLog "logs/{2}-access_log" common
{1}
''' . format(self.initMarkupVhosts, self.endMarkupVhosts, self.domain, self.pathDomain, alias)

		vhostsFile = open(self.envir["vhosts"], "a")
		vhostsFile.write(vhostsConfig)
		vhostsFile.close()

		hostsConfig = '''\n{0}\t{1}\n{0}\t{2}''' . format(self.envir["ipdomain"], self.domain, alias)

		hostsFile = open(self.envir["hosts"], "a")
		hostsFile.write(hostsConfig)
		hostsFile.close()	
			
		self.reloadApache()

		print "Done!"
		raw_input("Press any key to quit..")
		exit(1)

	def remove(self) :
		virtualHost = self.__removeVHosts(self.envir["vhosts"])
		hosts = self.__removeHosts(self.envir["hosts"])
		removedSuccess = ["Domain {0} removed from VirtualHost!" .format(self.domain), "Domain {0} removed from Hosts!" .format(self.domain)]
		
		if not virtualHost and not hosts :  
			print "Domain {0} not found in hosts and VirtualHost!" .format(self.domain)
			self.setDomain(True)

			#if domain is !Q then exit
			self.__VerifyRequestExit(self.domain)	
			
			virtualHost = self.__removeVHosts(self.envir["vhosts"])
			hosts = self.__removeHosts(self.envir["hosts"])	
		
		if not virtualHost :
			print "Domain {0} not found in VirtualHost!" .format(self.domain)
			removedSuccess.remove("Domain {0} removed from VirtualHost!" .format(self.domain))

		if not hosts :
			print "Domain {0} not found in Hosts!" .format(self.domain)	
			removedSuccess.remove("Domain {0} removed from Hosts!" .format(self.domain))

		for removed in removedSuccess :
			print removed
		
		self.reloadApache()
		print "Done!"
		raw_input("Press any key to quit..")
		exit(1)

	def listHosts(self) :
		hosts = []
		found = False

		#Create temp file
		virtualHosts = open(self.envir["vhosts"], "r")

		for line in virtualHosts:
			if found :
				if "ServerName " in line :
					hosts.append(line.replace("ServerName ", "").strip())

			if '<VirtualHost' in line  :			
				found = True

			if '</VirtualHost>' in line  :
				found = False
		
		virtualHosts.close()
		return hosts

	def __removeVHosts(self, file):
		foundMarkup = False
		foundDomain = False
		_found = False

		documentRoot = ""

		temp = []
		tempHost = []

		originalHost = open(file, 'r')
		for line in originalHost :

			if self.initMarkupVhosts in line  :
				foundMarkup = True

			if not foundMarkup : 
				temp.append(line)
			else :
				tempHost.append(line)

			if 'ServerName {0}' . format(self.domain) in line :
				foundDomain = True
				_found =True

			documentRoot = line.strip() if "DocumentRoot" in line else documentRoot
			
			if documentRoot and foundDomain :
				self.pathDomain = documentRoot.replace("DocumentRoot ", "") . replace('"', "")
				documentRoot = ""

			if self.endMarkupVhosts in line :
				if not foundDomain and tempHost :
					temp.append(''.join(tempHost))

				if "\n" == temp[-1] : 
					del temp[-1]
				tempHost = []	
				foundMarkup = False
				foundDomain = False	
		
		originalHost.close()

		if temp :
			originalHost = open(file, 'w+')
			originalHost.write('' . join(temp))		
			originalHost.close()

			#Remove dir
			self.__removeDir()

		return _found

	def __removeHosts(self, file):
		foundDomain = False
		temp = []
		tempHost = []

		originalHost = open(file, 'r')

		for line in originalHost :
			if not self.domain in line : 
				temp.append(line)
			else :
				foundDomain = True	
		else :
			if "\n" == temp[-1] : 
				del temp[-1]
		
		originalHost.close()

		if temp :
			originalHost = open(file, 'w+')
			originalHost.write('' . join(temp))		
			originalHost.close()

		return foundDomain		

	def __removeDir(self) :
		if os.path.exists(self.pathDomain) : 
			if raw_input("Remove path domain and all files from ('" + self.pathDomain + "') (y/n) ? : ").lower() == "y" : 
				shutil.rmtree(self.pathDomain)
				print "Dir {0} and files successfully removed!" . format(self.pathDomain)

	def __VerifyRequestExit(self, option, msg="") :
		if option.lower() == "!q" :
			print msg or "Ok! So long."
			os._exit(1)

	def reloadApache(self) :
		os.system(self.envir["apacherestart"])

	def createConfiguration(self) :
		configuredsEnvironments = []
		acceptedEnvironments = ["windows", "linux", "macos"]
		confs = open(self.confFile, "a")

		def processValue(msg, system, key) :
			confValue = raw_input(msg)

			if confValue :
				defaultsSystem = self.__getDefaultsSystem(system)
				confValue = Template(confValue)
				confValue = confValue.safe_substitute(HOME = defaultsSystem["defaulthome"], HOSTS = defaultsSystem["defaulthosts"], VHOSTS = defaultsSystem["defaultvhosts"], APACHERESTART = defaultsSystem["defaultapacherestart"], HTDOCS = defaultsSystem["defaulthtdocs"])
			
			elif not confValue : 
				confValue = Template(confValue)
				defaultsSystem = self.__getDefaultsSystem(system)
				return defaultsSystem["default{0}" . format(key.lower())]
			return confValue	 
								
		while True : 
			environment = raw_input("Set to which environment(%s) ? : " % ('|'.join(acceptedEnvironments)),)
			
			if environment in configuredsEnvironments :
				print "Environment already configured!"

			if environment.lower() == "!q" :
				if len(configuredsEnvironments) > 0 :
					print "configured environment: "
					for configuredEnvironment in configuredsEnvironments :
						print configuredEnvironment

					if not self.__platform in configuredsEnvironments :
						if raw_input("You do not set the configuration for your operating system, it's ok? Configure now?(Y/n) : ").lower() == "n" :
							break
						else :
							environment = self.__platform
					else :
						break		
				else : 
					print "You have not set any environment!"
					confs.close()
					remove(self.confFile)
					raw_input("Press any key to quit..")
					exit(1)		

			if environment in acceptedEnvironments:
				print """\n**Note: Defaults for {0}\n
$HOME - {1}
$HOSTS - {2}
$VHOSTS - {3}
$APACHERESTART - {4}
$HTDOCS - {5}
""" . format(environment, self.__getDefaultsSystem(environment)["defaulthome"], self.__getDefaultsSystem(environment)["defaulthosts"], self.__getDefaultsSystem(environment)["defaultvhosts"], self.__getDefaultsSystem(environment)["defaultapacherestart"], self.__getDefaultsSystem(environment)["defaulthtdocs"])
			
				#Init write
				confs.write("[%s]\n" % (environment.upper(),))

				confValue = processValue("Enter the full path to the host file: ", environment, "hosts")
				confs.write('conf.{0}.hosts = "{1}"\n' . format(environment, confValue))
			
				confValue = processValue("Enter the full path to the vhosts file: ", environment, "vhosts")
				confs.write('conf.{0}.vhosts = "{1}"\n' . format(environment, confValue))

				confs.write('conf.{0}.ipdomain = "{1}"\n' . format(environment, raw_input("Default ipdomain[127.0.0.1]: ") or "127.0.0.1"))	
				confs.write('conf.{0}.domainport = "{1}"\n' . format(environment, raw_input("Default port of domain[80]: ") or "80"))
				
				confValue = processValue("Base path for sites: ", environment, "htdocs")
				confs.write('conf.{0}.basepathdomain = "{1}"\n' . format(environment, confValue))

				confValue = processValue("Apache Restart command: ", environment, "apacherestart")
				confs.write('conf.{0}.apacherestart = "{1}"\n' . format(environment, confValue))
				#End Write

				configuredsEnvironments.append(environment)
				
				if len(configuredsEnvironments) == len(acceptedEnvironments) : 
					print "All are configured environments!"
					break

		confs.close()

	def __getDefaultsSystem(self, system) :
		return self.defaultssystem[system];		
			
	def __setDefaultsSystem(self) :
		self.defaultssystem["windows"]["defaulthome"] = r"C:\Users\{0}" . format(self.__getUsername()) 
		self.defaultssystem["windows"]["defaulthosts"] =  r"C:\Windows\system32\drivers\etc\hosts"
		self.defaultssystem["windows"]["defaultvhosts"] = r"C:\xampp\apache\conf\extra\httpd-vhosts.conf"
		self.defaultssystem["windows"]["defaultapacherestart"] = r'C:\xampp\apache\bin\httpd.exe -k restart'
		self.defaultssystem["windows"]["defaulthtdocs"] = r"C:/xampp/htdocs"

		self.defaultssystem["linux"]["defaulthome"] = r"/home/{0}" . format(self.__getUsername())
		self.defaultssystem["linux"]["defaulthosts"] =  r"/etc/hosts"
		self.defaultssystem["linux"]["defaultvhosts"] = r"opt/lampp/etc/extra/httpd-vhosts.conf"
		self.defaultssystem["linux"]["defaultapacherestart"] = r"sh /opt/lampp/lampp restart"
		self.defaultssystem["linux"]["defaulthtdocs"] = r"/opt/lampp/htdocs"

		self.defaultssystem["macos"]["defaulthome"] = r"/Users/{0}" . format(self.__getUsername())
		self.defaultssystem["macos"]["defaulthosts"] =  r"/etc/hosts"
		self.defaultssystem["macos"]["defaultvhosts"] = r"/Applications/XAMPP/xamppfiles/etc/extra/httpd-vhosts.conf"
		self.defaultssystem["macos"]["defaultapacherestart"] = r"sh /Applications/XAMPP/xamppfiles/xampp reloadapache"
		self.defaultssystem["macos"]["defaulthtdocs"] = r"/Applications/XAMPP/xamppfiles/htdocs"

	def __getUsername(self) :
		if self.__platform != "windows" :
			return os.getenv("SUDO_USER") or pwd.getpwuid(os.getuid())[0] 
		else :	
			import getpass
			return getpass.getuser()
    			
#Start
def main():
	App = ManageHosts()
	try:
		opts, args = getopt.getopt(sys.argv[1:], "lc:r:h", ["help"])
	except getopt.error, msg:
		print msg
		print "for help use --help"
		sys.exit(2)
	
	# process options
	for o, v in opts:
		if o in ("-h") :
			print App.__doc__
		if o in ("-r", "-c", "-l") :
			if "--help" in v :
				print "Enter the domain name"
				sys.exit(0)
			App.selectOption(o, v)	

	if not opts and not args : 
		App.start()

if __name__ == "__main__":
    main()