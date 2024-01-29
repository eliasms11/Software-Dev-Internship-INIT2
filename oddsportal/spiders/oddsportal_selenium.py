import scrapy
from scrapy.selector import Selector
from selenium import webdriver
from shutil import which
from selenium.webdriver.chrome.options import Options
import csv
from pathlib import Path
import os
import json
import telegram
from scrapy.crawler import CrawlerProcess


class OddsportalSpiderSelenium(scrapy.Spider):
    name = 'oddsportal_selenium'
    allowed_domains = ['www.oddsportal.com']
    start_urls = ['https://www.oddsportal.com/matches/soccer']

    custom_settings = {"FEEDS": {"matches.csv": {"format": "csv"}}}

    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")

        chrome_path = which("chromedriver")
        driver = webdriver.Chrome(executable_path=chrome_path, options=chrome_options)
        driver.get("https://www.oddsportal.com/matches/soccer")

        self.html = driver.page_source
        driver.close()

    def parse(self, response):
        resp = Selector(text=self.html)
        for partido in resp.xpath("//div[@id='table-matches']/table/tbody/tr[@class!='dark center']/td[@class='name table-participant']/a[1]/span[contains(@class,'live')]/parent::a/parent::td/parent::tr"):
            pais = partido.xpath(
                ".//preceding::tr[contains(@class, 'dark center')][1]/th/a[@class='bfl']/text()").get()
            division = partido.xpath(
                ".//preceding::tr[contains(@class, 'dark center')][1]/th/a[2]/text()").get()
            equipos = partido.xpath(
                ".//td[@class='name table-participant']/a/text()").get()
            minuto = partido.xpath(
                ".//td[contains(@class, 'table-time')]/text()").get()
            resultado = partido.xpath(".//td[contains(@class, 'table-score live-score')]/span/text()").get()
            cuota_local = partido.xpath(".//td[@class='odds-nowrp'][1]/@xodd").get()
            cuota_empate = partido.xpath(".//td[@class='odds-nowrp'][2]/@xodd").get()
            cuota_visitante = partido.xpath(".//td[@class='odds-nowrp'][3]/@xodd").get()
            codigo_partido = partido.xpath(".//td[@class='name table-participant']/a/@href").get()

            yield {
                'Country': pais,
                'League': division,
                'Match': equipos,
                'Minute': minuto,
                'Score': resultado,
                'local': cuota_local,
                'empate': cuota_empate,
                'visitante': cuota_visitante,
                'codigo': codigo_partido
            }


def match_code(link: str): # FUNCION PARA OBTENER EL CODIGO A PARTIR DEL LINK
    codigo = ""
    slashes = 0
    hyphens = 0
    for i in range(len(link) - 1, -1, -1):
        if link[i] == "/":
            slashes += 1
        if link[i] == "-":
            hyphens += 1
        if hyphens == 2:
            break
        if slashes == 2 and hyphens == 1 and link[i] != '/':
            codigo += link[i]
    code = codigo[::-1]
    return code


def code_and_res(matches): # FUNCION PARA OBTENER LAS DOS LISTAS CON CODIGOS DE PARTIDOS Y MARCADORES YA ANOTADOS ANTERIORMENTE
    codes = []
    results = []
    for line in matches:
        linea = line.strip().split(',')
        codes.append(linea[0])
        marcador = linea[1].strip().split(':')
        results.append(marcador)
    return codes, results


# FUNCION QUE EVALUA SI UN PARTIDO CUMPLE LOS REQUISITOS PARA SER ENVIADO AL BOT O NO


def mostrar(local: int, visitante: int, cuota_local: float, cuota_visitante: float, code: str, prev_codes, prev_res):
    if code not in prev_codes:
        if cuota_local < cuota_visitante and visitante > local:
            return True
        if cuota_visitante < cuota_local and local > visitante:
            return True
    else:
        for i in range(len(prev_codes) -1, -1, -1):
            if code == prev_codes[i]:
                marcador_previo = prev_res[i]
                prev_local = int(marcador_previo[0])
                prev_vis = int(marcador_previo[1])
                if local == prev_local and visitante == prev_vis:
                    return False
                else:
                    return True
    return False


def read_matches(f): # FUNCION QUE LEE DE LA SALIDA DEL SCRAPER (FICHERO) TODOS LOS PARTIDOS PARA VER CUALES SON APTOS
    file = open(f, 'r', encoding='utf-8')
    csvreader = csv.reader(file)
    rows = []
    if os.stat("matches.csv").st_size == 0:
        return rows
    else:
        header = [next(csvreader)]
        cods = set()
        anotados_path = Path("noted.csv")
        prev_codes = []
        prev_res = []
        if not anotados_path.is_file():
            vistos = open("noted.csv", 'a+', encoding='utf-8')
            vistos.close()
        else:
            vistos = open("noted.csv", 'r', encoding='utf-8')
            if os.stat("noted.csv").st_size != 0:
                partidos_vistos = vistos.readlines()
                prev_matches = code_and_res(partidos_vistos)
                prev_codes = prev_matches[0]
                prev_res = prev_matches[1]

        for row in csvreader:
            if row[2] == "":
                row[2] = "-"
            if row[3] == "":
                row[3] = "0"
            minute = row[3]
            if row[4] == "":
                row[4] = 0
            score = row[4]
            marcador = []
            if (":" not in minute or minute == "HT") and score != 0 and score != "Score":
                marc = score.strip().split(':')
                for g in marc:
                    marcador.append(int(g))
                local = marcador[0]
                visitante = marcador[1]
                cuota_local = float(row[5])
                cuota_visitante = float(row[7])
                code = match_code(row[8])
                if mostrar(local, visitante, cuota_local, cuota_visitante, code, prev_codes, prev_res):
                    vistos = open("noted.csv", 'a+', encoding='utf-8')
                    rows.append(row)
                    new_match = code + ',' + score + '\n'
                    vistos.write(new_match)
                    vistos.close()
        #if len(rows) == 0: # NECESARIO PARA NOTIFICAR PARTIDOS SIN CAMBIOS EN EL RESULTADO O QUE NO CUMPLEN LAS CARACTERISTICAS
         #   rows.append(-1)
    return rows


def notify_ending(message): # FUNCION PARA ENVIAR A TELEGRAM
    with open('keys.json', 'r') as keys_file:
        k = json.load(keys_file)
        token = k['telegram_token']
        chat_id = k['telegram_chat_id']
    bot = telegram.Bot(token=token)
    bot.sendMessage(chat_id=chat_id, text=message)


def send_telegram(matches): # FORMATO DEL MENSAJE QUE SE ENVIA AL BOT
    mensajes = []
    if len(matches) == 0:
        notify_ending("NO ONGOING MATCHES / NO CHANGES")
    else:
        '''
        if len(matches) == 1 and matches[0] == -1:  # NECESARIO PARA NOTIFICAR PARTIDOS SIN CAMBIOS EN EL RESULTADO O QUE NO CUMPLEN LAS CARACTERISTICAS
            notify_ending("NO FAVORABLE MATCHES / UNCHANGED RESULTS")
        else:'''
        for partido in matches:
            mensaje_partido = "League:  {0} >> {1}\nMatch:  {2}\nMinute:  {3}'\nScore:  {4}\nOdds:\n1          X          2\n{5}       {6}      {7}".format(
                partido[0], partido[1], partido[2], partido[3], partido[4], partido[5], partido[6], partido[7])
            mensajes.append(mensaje_partido)
        for m in mensajes:
            notify_ending(m)


def ejec(main_leagues: int):  # FUNCION QUE MANEJA EL FICHERO DE PARTIDOS, SU LECTURA Y EL ENVIO DE RESULTADOS AL BOT
    file = Path("matches.csv")
    if file.is_file():
        os.remove("matches.csv")
    process = CrawlerProcess({
        'USER_AGENT':  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'})
    process.crawl(OddsportalSpiderSelenium)
    process.start()
    my_file = Path("matches.csv")
    if my_file.is_file():
        partidos = read_matches("matches.csv")
        seleccionados = []
        principales = ["LaLiga", "LaLiga2", "Serie A", "Serie B", "Bundesliga", "2. Bundesliga", "Ligue 1", "Ligue 2", "Liga Portugal", "Liga Portugal 2", "Premier League", "Championship"]
        paises = ["Spain", "Italy", "Germany", "France", "Portugal", "England"]
        if main_leagues == 1:
            for p in partidos:
                if p[0] in paises:
                    if p[1] in principales:
                        seleccionados.append(p)
            send_telegram(seleccionados)
        else:
            send_telegram(partidos)

# PROGRAMA PRINCIPAL


if __name__ == '__main__':
    file = Path("select.txt")
    if file.is_file():
        f = open("select.txt", "r")
        line = f.readline()
        if line == "1":
            ejec(1)
        else:
            ejec(0)
    else:
        ejec(0)
