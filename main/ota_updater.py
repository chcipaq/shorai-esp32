import os
import gc
import machine
from main import mrequests

header = {
    'User-Agent': 'My User Agent 1.0',
    'From': 'youremail@domain.com' 
}


class OTAUpdater:

    def __init__(self, github_repo, module='', main_dir='main'):
        self.github_repo = github_repo.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
        self.main_dir = main_dir
        self.module = module.rstrip('/')

    @staticmethod
    def using_network(ssid, password):
        import network
        sta_if = network.WLAN(network.STA_IF)
        if not sta_if.isconnected():
            print('connecting to network...')
            sta_if.active(True)
            sta_if.connect(ssid, password)
            while not sta_if.isconnected():
                pass
        print('network config:', sta_if.ifconfig())

    def check_for_update_to_install_during_next_reboot(self, ssid, password):
        OTAUpdater.using_network(ssid, password)
        #current_version = '1.1'
        current_version = self.get_current_version()
        latest_version = self.get_latest_version()
        #latest_version = '1.3'

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        if latest_version != current_version and latest_version != 'not-received':
            print('New version available, will download and install on next reboot')
            self.mkdir_f(self.modulepath('next'))
            with open(self.modulepath('next/.version_on_reboot'), 'w') as versionfile:
                versionfile.write(latest_version)
                versionfile.close()

    def download_and_install_update_if_available(self, ssid, password):
        if 'next' in os.listdir(self.module):
            if '.version_on_reboot' in os.listdir(self.modulepath('next')):
                latest_version = self.get_version(self.modulepath('next'), '.version_on_reboot')
                print('New update found: ', latest_version)
                self._download_and_install_update(latest_version, ssid, password)
        else:
            print('No new updates found...')

    def _download_and_install_update(self, latest_version, ssid, password):
        OTAUpdater.using_network(ssid, password)

        self.download_all_files(self.github_repo + '/contents/' + self.main_dir, latest_version)
        self.rmtree(self.modulepath(self.main_dir))
        os.rename(self.modulepath('next/.version_on_reboot'), self.modulepath('next/.version'))
        os.rename(self.modulepath('next'), self.modulepath(self.main_dir))
        print('Update installed (', latest_version, '), will reboot now')
        machine.reset()

    def apply_pending_updates_if_available(self):
        if 'next' in os.listdir(self.module):
            if '.version' in os.listdir(self.modulepath('next')):
                pending_update_version = self.get_version(self.modulepath('next'))
                print('Pending update found: ', pending_update_version)
                self.rmtree(self.modulepath(self.main_dir))
                os.rename(self.modulepath('next'), self.modulepath(self.main_dir))
                print('Update applied (', pending_update_version, '), ready to rock and roll')
            else:
                print('Corrupt pending update found, discarding...')
                self.rmtree(self.modulepath('next'))
        else:
            print('No pending update found')

    def download_updates_if_available(self):
        current_version = self.get_current_version()
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        if latest_version > current_version:
            print('Updating...')
            self.mkdir_f(self.modulepath('next'))
            self.download_all_files(self.github_repo + '/contents/' + self.main_dir, latest_version)
            with open(self.modulepath('next/.version'), 'w') as versionfile:
                versionfile.write(latest_version)
                versionfile.close()

            return True
        return False

    def rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self.rmtree(directory + '/' + entry[0])

            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def get_current_version(self):
        return  self.get_version(self.modulepath(self.main_dir))

    def get_version(self, directory, version_file_name='.version'):
        if version_file_name in os.listdir(directory):
            f = open(directory + '/' + version_file_name)
            version = f.read()
            f.close()
            return version
        return '0.0'


    def get_latest_version(self):
        import urequests
        string = urequests.get(self.github_repo + '/releases/latest', headers= header)
        version = string.json().get('tag_name', 'not-received')
        string.close()
        return version
    

    def download_all_files(self, root_url, version):
        file_list = mrequests.get(root_url + '?ref=refs/tags/' + version,  headers=header)
        # {b"Accept": b"application/json", b"User-Agent": b"MicroPython OTAUpdater"}
        for file in file_list.json():
            if file['type'] == 'file':
                download_url = file['download_url']
                download_path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                self.download_file(download_url.replace('refs/tags/', ''), download_path)
            elif file['type'] == 'dir':
                path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                self.mkdir_f(path)
                self.download_all_files(root_url + '/' + file['name'], version)

        file_list.close()

    def download_file(self, url, path):
        print('\tDownloading: ', path)
        r = mrequests.get(url)
        r.save(path)
        r.close()
        gc.collect()

    def modulepath(self, path):
        return self.module + '/' + path if self.module else path
    
    def mkdir_f(self, path):
        try:
            os.mkdir(path)
        except OSError as exc:  # Python ≥ 2.5
            if exc.errno == errno.EEXIST:
                pass
            # possibly handle other errno cases here, otherwise finally:
            else:
                raise
