#!/usr/bin/env python3
## Original work: @s0lst1c3
## Reworked by @RackunSec - 2022
##
## Import modules:
import os ## path(), etc
import sys ## exit(), argv, etc
import subprocess ## Running commands with run_cmd(ARRAY)
from git import Repo ## for git
import requests ## Downloading files
from sty import fg ## Colors!
from settings import settings ## Reading settings files
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) ## Supress self-signed certs warnings
from rich.status import Status
import shutil ## move a directory with it's contents
import signal ## CTRL+C handling

class EapHammer:
    def __init__(self):
        self.default_wordlist = os.path.join(settings.dict['paths']['directories']['wordlists'], settings.dict['core']['eaphammer']['general']['default_wordlist'])
        self.wordlist_source = settings.dict['core']['eaphammer']['general']['wordlist_source']
        self.dependencies_list=os.getcwd()+"/dependencies.list"
        self.root_dir = settings.dict['paths']['directories']['root']
        self.local_dir = settings.dict['paths']['directories']['local']
        self.openssl_source = settings.dict['core']['eaphammer']['general']['openssl_source'].replace("'","") ## remove the single quotes
        self.openssl_version = settings.dict['core']['eaphammer']['general']['openssl_version']
        self.openssl_build_options = settings.dict['core']['eaphammer']['general']['openssl_build_options']
        self.openssl_build_prefix = os.path.join(self.local_dir, 'openssl/local')
        self.openssl_bin = settings.dict['paths']['openssl']['bin'] ## Local install which is backwards compatible with SSL3
        self.dh_file = settings.dict['paths']['certs']['dh']
        self.RED=fg(197) ## Red Text
        self.GREEN=fg(82) ## Green Text
        self.RST='\033[0m' ## Reset color to default

    ## CTRL+C
    def signal_handle(self,signum,frame):
        print(f"\n{self.RED}[!] CTRL+C Pressed ({signum}).\n[!] You may have to delete and clone repo to start over if EAPHammer is not working.{self.RST}\n\n")
        sys.exit()

    ## Confirm With User:
    def confirm(self):
        print(f"[!] {self.RED}Important:{self.RST} it is highly recommended that you run `{self.RED}apt -y update{self.RST}` and `{self.RED}apt -y upgrade{self.RST}` prior to running this setup script.")
        if input(f"[?] Do you wish to proceed? Enter [y/N]: ").lower() == "y":
            return True

    ## Download a file:
    def download_file(self,uri,path):
        try:
            if os.path.exists(path): ## Already downloaded, let's destroy it
                print(f"  -- path already existed, {path}, deleting file.")
                os.unlink(path)
            response = requests.get(uri,verify=False)
            with open(path,"wb") as downloaded_file:
                downloaded_file.write(response.content)
            return True
        except Exception as e:
            self.fatal_error(f"Could not download file: {uri} {e}")
            return False

    ## Git CLone:
    def git_clone(self,uri,path,repo_dir):
        if os.path.isdir(path): ## Path exists, let's make a repo in it:
            try:
                print(f"  -- Cloning to local repository: {path+'/'+repo_dir}")
                if os.path.exists(path+"/"+repo_dir):
                    print(f"  -- Repository already exists: "+path+"/"+repo_dir+" ",end="")
                    return
                Repo.clone_from(uri, path+"/"+repo_dir)
                return True
            except Exception as e:
                print(e)
                return False

    ## Check if root:
    def exit_if_not_root(self):
        if os.getuid() != 0:
            sys.fatal_error("This script must be run as root.")
        return True

    ## Fatal errors:
    def fatal_error(self,msg):
        print(f"\n[!] {self.RED}{msg}{self.RST}")
        sys.exit(1)
        return

    ## Read dependencies file:
    def read_deps_file(self,deps_file):
        if os.path.exists(deps_file): 
            with open(deps_file) as fd:
                return ' '.join([ line.strip() for line in fd ])
        else:
            self.fatal_error(f"Could not open file {deps_file}")

    ## Run a command:
    def run_cmd(self,cmd):
        ##print(f"[i] Running command: {cmd}") ## DEBUG
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return

    ## Install packages via APT:
    def apt_install(self,packages):
        ##print(packages) ## DEBUG
        packages.insert(0,"apt")
        packages.insert(1,"install")
        packages.insert(2,"-y")
        packages.insert(3,"--assume-yes")
        subprocess.run( ## Uncomment the DEVNULL lines to debug
            packages,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL) ## Install stuff
        return

    ## Check if installation(s) were successful:
    def check_status(self,app,app_file):
        ##print(f"  -- Checking for existence of file: {app_file}: ",end="") ## DEBUG
        if os.path.exists(app_file): ## check for existence of file
            print(f"[i] {app} {self.GREEN}Successful.{self.RST}")
            return True
        else:
            self.fatal_error(f"{self.RED}Failed to install {app}. Exiting.{self.RST}")
        return

    def install_all(self):
        ## TODO (check if actually deleted):
        print('\n[i] Removing stub files. ')
        self.run_cmd(["find",f"{self.root_dir}","-type","f","-name","'stub'","-exec","rm","-f",'{}',"+"])

        signal.signal(signal.SIGINT,self.signal_handle) ## incase CTRL+C is pressed during work.
        
        ## Apt install Dependencies:
        with Status(f" Installing Dependencies via APT ... ") as status:
            if os.path.exists(self.dependencies_list):
                with open(self.dependencies_list,"r") as deps_list:
                    apt_list_array=[]
                    for line in deps_list.readlines():
                        apt_list_array.append(line.strip())
                    self.apt_install(apt_list_array)
            else:
                fatal_error(f" -- Could not read {self.dependencies_list}")

            self.run_cmd(["apt","-y","install","$(cat )"])
            self.check_status("Apt Dependencies","/usr/sbin/apache2")

        ## Python Dependencies:
        with Status(' Installing Python dependencies ... ') as status:
            self.run_cmd(["python3","-m","pip","install","-r","requirements.txt"])
            self.check_status("Python3 Dependencies","/usr/local/lib/python3.9/dist-packages/jinja2/tests.py")    

        ## Old OpenSSL - For SSLv3 Without Overwriting System-Wide Installation:
        with Status(f" Generating local version of OpenSSL (OpenSSL_{self.openssl_version.replace('.', '_')})") as status:
            self.download_file(self.openssl_source,self.local_dir+"/openssl.tar.gz")
            os.chdir(self.local_dir) ## local_dir is s0lst1c3's build directory
            self.run_cmd(["tar","vzxf","openssl.tar.gz"])
            try:
                shutil.move(self.local_dir+"/openssl-OpenSSL_"+self.openssl_version.replace('.', '_').replace("'",""),self.local_dir+"/openssl") ## rename the directory to "openssl"
            except: ## path exists
                pass
            ##     os.system('mv {local_dir}/openssl-OpenSSL_{openssl_version.replace('.', '_')} {local_dir)}/openssl'
            os.unlink(self.local_dir+"/openssl.tar.gz") ## remove the tarball
            os.chdir(self.local_dir+"/openssl") ## go into the directory
            self.run_cmd(["./config",f"--prefix={self.openssl_build_prefix}","enable-ssl2","enable-ssl3","enable-ssl3-method","enable-des","enable-rc4","enable-weak-ssl-ciphers","no-shared"])
            os.chdir(self.local_dir+"/openssl") ## go into the director
            self.run_cmd(["make"])
            os.chdir(self.local_dir+"/openssl") ## go into the director
            self.run_cmd(["make","install_sw"])
            self.check_status("OpenSSL",self.local_dir+"/openssl/apps/openssl") ## UPDATE ME

        ## Create Diffie Hellman File:
        with Status(' Create DH parameters file with default length of 2048 ...  ') as status:
            self.run_cmd([self.openssl_bin,"dhparam","-out",self.dh_file,"2048"])
            self.check_status("DH Configure",self.dh_file)

        ## HostAPd:
        with Status(" Compiling hostapd ... ") as status:
            os.chdir(settings.dict['paths']['directories']['hostapd'])
            self.run_cmd(["cp","defconfig",".config"])
            self.run_cmd(["make","hostapd-eaphammer_lib"])
            self.run_cmd(["make"])
            self.check_status("HostAPd",os.getcwd()+"/hostapd-eaphammer")

        ## HCXTools:
        with Status(" Compiling hcxtools ...  ") as status:
            os.chdir(settings.dict['paths']['directories']['hcxtools'])
            self.run_cmd(["make"])
            self.check_status("HCXTools",os.getcwd()+"/hcxpcaptool")

        ## HCXDump Tool:
        with Status(" Compiling hcxdumptool ... ") as status:
            os.chdir(settings.dict['paths']['directories']['hcxdumptool'])
            self.run_cmd(["make"])
            self.check_status("HCXDumpTool",os.getcwd()+"/hcxdumptool")

        ## Default word list: 
        with Status(' Downloading default wordlist ... ') as status:
            self.download_file(self.wordlist_source,self.default_wordlist+".tgz") ## Download the file
            self.check_status("Default Wordlist",self.default_wordlist+".tgz") ## Check if it downloaded
            os.chdir(settings.dict['paths']['directories']['wordlists']) ## go to it's location
            self.run_cmd(["tar","vzxf",self.default_wordlist+".tgz"]) ## untar it

        ## Responder:
        with Status(" Retrieving Responder ... ") as status:
            self.git_clone("https://github.com/lgandx/Responder.git",settings.dict['paths']['directories']['local'],"Responder")
            self.check_status("Responder",settings.dict['paths']['directories']['local']+"/Responder/Responder.py")

        ## Captive Portal Symlink:
        with Status(' Creating symlink to captive portal template directory ... ') as status:
            try:
                os.symlink(settings.dict['paths']['wskeyloggerd']['usr_templates'],
                    settings.dict['paths']['wskeyloggerd']['usr_templates_sl'])
            except FileExistsError as e:
                print("  -- Symlink file already exists: ",end="")
                self.check_status("Symlink for Captive Portal",settings.dict['paths']['wskeyloggerd']['usr_templates_sl'])

        ## Done
        print(f"[i] {self.GREEN}EAPHammer Setup Completed Successfully.{self.RST}\n")


if __name__ == '__main__':
    print("\n *** EAPHammer Setup Script - 2022 *** \a\n")
    eaphammer=EapHammer()
    eaphammer.exit_if_not_root()
    if "-y" not in sys.argv:
        if eaphammer.confirm():
            eaphammer.install_all()
    else:
        eaphammer.install_all()




