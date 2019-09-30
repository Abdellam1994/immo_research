import urllib2
from selenium import webdriver
import re
import json
from multiprocessing import Pool
import yaml
import requests
from itertools import cycle


class SeLoger():
    def __init__(self, selenium=False, use_proxy_rotator=False, path_config_file="research_config.yaml"):
        self.research_config = self.read_config_file(path_config_file)
        self.start_url = self.get_start_url_from_config(self.research_config)
        self.start_url = "https://www.seloger.com/list.htm?types=1&projects=2&enterprise=0&natures=1%2C4&price=150000%2F300000&surface=15%2F30&rooms=1&places=%5B%7Bcp%3A75%7D%5D&qsVersion=1.0&LISTING-LISTpg=1"
        self.selenium = selenium

        if self.selenium:
            options = webdriver.ChromeOptions()
            options.add_argument('headless')
            self.driver = webdriver.Chrome(options=options)

        self.num_workers = 10

    def read_config_file(self, path_config_file):
        research_config = yaml.safe_load(open(path_config_file, "r"))
        return research_config

    def get_start_url_from_config(self, config_file):
        min_budget_default, max_budget_default = 0, 50000000
        min_surface_default, max_surface_default = 0, 300

        min_budget = config_file["budget"].get("min_budget", min_budget_default)
        max_budget = config_file["budget"].get("max_budget", max_budget_default)
        min_surface = config_file["surface"].get("min_surface", min_surface_default)
        max_surface = config_file["surface"].get("max_surface", max_surface_default)

        start_url = "https://www.seloger.com/list.htm?types=1&projects=2&enterprise=0&natures=1%2C4&price={min_budget}%2F{max_budget}&surface={min_surface}%2F{max_surface}&rooms=1&places=%5B%7Bcp%3A75%7D%5D&qsVersion=1.0&LISTING-LISTpg=1".format(min_budget=min_budget, max_budget=max_budget,
                                                                                                                                                                                                                                                      min_surface=min_surface, max_surface=max_surface)
        return start_url

    def get_page_from_url(self, url, selenium=False):
        if selenium:
            self.driver.get(url)
            page = self.driver.page_source
            return page

        headers = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
        req = urllib2.Request(url, '', headers)
        page = urllib2.urlopen(req).read()
        print(page)
        # TODO : proxy
        import utils
        proxies = utils.get_proxies()
        proxy_pool = cycle(proxies)
        for i in range(1, 11):
            # Get a proxy from the pool
            proxy = next(proxy_pool)
            print(proxy)
            try:
                response = requests.get(url, proxies={"http": proxy, "https": proxy})
                print(response.json())
            except:
                print("Skipping. Connnection error")
        page = response.text
        return page

    def get_pages_ids(self, url):
        page = self.get_page_from_url(url, self.selenium)
        all_ids_raw = re.findall(r'idannonce=\d+', page)
        all_ids = [int(id_raw.split("=")[1]) for id_raw in all_ids_raw]
        return list(set(all_ids))

    @staticmethod
    def get_info_announce(id_annonce):
        url_general = "https://www.seloger.com/funding,json,annonce_details.json?idannonce={id_annonce}".format(id_annonce=id_annonce)
        url_details = "https://www.seloger.com/detail,json,caracteristique_bien.json?idannonce={id_annonce}".format(id_annonce=id_annonce)
        general_info = json.loads(urllib2.urlopen(url_general).read())
        details_info = json.loads(urllib2.urlopen(url_details).read())
        info_announce = general_info
        info_announce.update(details_info)
        return info_announce

    def get_info_from_ids_announces(self, ids_announces):
        data_url = {}
        for id_announce in ids_announces:
            data_url[id_announce] = self.get_info_announce(id_announce)
        return data_url

    def get_info_url_parallel_from_ids_announces(self, ids_announces):
        data_url = {}
        datas = Pool.map(self.get_info_announce, ids_announces)
        for id_announce, data in zip(ids_announces, datas):
             data_url[id_announce] = data
        return data_url

    def get_info_url(self, url, parallel=False):
        ids_announces = self.get_pages_ids(url)
        if parallel:
            data_url = self.get_info_url_parallel_from_ids_announces(ids_announces)
            return data_url
        data_url = self.get_info_from_ids_announces(ids_announces)
        return data_url

    @staticmethod
    def get_next_page_url(url):
        split_term = "pg="
        url_base, page_nb = url.split(split_term)
        url_next_page = url_base + "pg={}".format(int(page_nb) + 1)
        return url_next_page

    def run(self, n_lim=5):
        i = 0
        current_url = self.start_url
        d_data = {}
        while i < n_lim:
            i += 1
            data_url = self.get_info_url(current_url)
            if data_url == {}:
                return d_data
            d_data.update(data_url)
            current_url = self.get_next_page_url(current_url)

        return d_data

    def parse_criterias_variable(self, criterias):
        d_out = {}
        for criteria in criterias:
            for elem in criteria["criteria"]:
                d_out[elem["order"]] = d_out[elem["value"]]

        return d_out
