# -*- coding: utf-8 -*-
from datetime import datetime, date
import os
import requests
from bs4 import BeautifulSoup
from telegraph import Telegraph
from telegraph.exceptions import TelegraphException
from config import teletoken, BASE_DIR
import json
import users_controller
import flag


def get_team_foot_url(team_name):
    with open('footlinks.json', 'r') as file:
        data = json.load(file)
        url = data[team_name]['foot_link']

    return url


def get_countries_dict():
    with open('country.json', 'r') as file:
        data = json.load(file)

    return data


#parses all information about next match
def parse_next_match(team_name):
    url = get_team_foot_url(team_name)

    page = requests.get(url)
    html = page.text

    soup = BeautifulSoup(html, 'lxml')

    next_match = {}

    #scrapes next matches table
    next_matches = soup.find_all('table', class_='feed-table')[1]\
                       .find_all('tr')

    next_match_where = [' '.join(part.split()) for part in next_matches[0].find('p').get_text().split('\n')[1:-1]]

    next_match['date'] = next_match_where[0]
    next_match['tournament'] = next_match_where[1]
    next_match['stage'] = next_match_where[2]

    #scrapes info about home and guest teams and time of the match
    next_match['time'] = next_matches[1].find_all('td')[0].get_text()
    next_match['home'] = ' '.join(next_matches[1].find_all('td')[1].get_text().split())

    next_match['guest'] = ' '.join(next_matches[1].find_all('td')[3].get_text().split())

    return next_match


#parses general information about next match
def parse_info(team_name):
    next_match = parse_next_match(team_name)

    return "📌 *Следующий матч*\n⚽ {} — {}\n🏆 {}, {}\n📅 {}, {}"\
                                .format(next_match['home'], next_match['guest'], next_match['tournament'], \
                                        next_match['stage'], next_match['date'], next_match['time'])


#parse remaining time before next match
def parse_time(team_name):
    next_match = parse_next_match(team_name)
    date, time = next_match['date'], next_match['time']

    day = int(date.split('.')[0])
    month = int(date.split('.')[1])
    year = int(date.split('.')[2])

    hours = int(time.split(':')[0])
    minutes = int(time.split(':')[1])

    now = datetime.now()    #exact time when request made
    match_date = datetime(year, month, day, hours, minutes, 0)

    time_left = match_date - now    #calculate remaining time

    hours = time_left.seconds // 3600
    minutes = (time_left.seconds % 3600) // 60

    endings = get_endings(time_left.days, hours, minutes)

    message_text = 'До следующего матча {} {} {}, {} {}, {} {}'.format(endings[0],
                                                         time_left.days, endings[1],
                                                         hours, endings[2],
                                                         minutes, endings[3])

    return message_text


def get_endings(*values):
    endings = []
    left_message = ['остался', 'осталось']
    values_end_with_1 = ['день', 'час', 'минута']
    values_end_with_234 = ['дня', 'часа', 'минуты']
    other_values = ['дней', 'часов', 'минут']

    for i, value in enumerate(values):
        remainder = value % 10
        if remainder == 1:
            if i == 0:
                endings.append(left_message[0])
            endings.append(values_end_with_1[i])
        elif remainder in range(2, 5):
            if i == 0:
                endings.append(left_message[1])
            endings.append(values_end_with_234[i])
        else:
            if i == 0:
                endings.append(left_message[1])
            endings.append(other_values[i])

    return endings


#function for parsing article
def parse_article(url, too_big=False):
    content = ''
    page = requests.get(url)
    url = page.url

    html = page.text

    soup = BeautifulSoup(html, 'lxml')
    article = soup.find_all('article')[0]

    title = article.find_all('h1')[0].text  #title of article
    paragraphs = article.find_all('p')[1:]  #all useful text from article

    header = article.find('div', class_='news-header-top')
    if header:
        img = header.find('img')
        if img:
            content += "<img src='{}'></img>".format('/'.join(url.split('/')[:3]) + img['src'])

    for p in paragraphs:
        if 'img' in str(p):
            image_url = p.find('img')['src']    #get image's url
            content += "<img src='{}'></img>".format(image_url)    #create image path appr. for Telegraph

        if('span' not in str(p)):  #'span' tag is not allowed in telegraph
            content += str(p)

        if 'class="intro"' in str(p):  #get article photo
            image_url = article.find('div', class_='article-photo')\
                               .find('img')['src']
            content += "<img src='{}'></img>".format(image_url)
            content += str(p)

    #if article is too big we split it into two different Instant Views
    if too_big:
        content_list = content.split('<p')  #split all paragraphs
        middle = int(len(content_list) / 2) #middle of all paragraphs

        content1 = '<p'.join(content_list[:middle]) #first page

        content_list[middle] = '<p' + content_list[middle]
        content2 = '<p'.join(content_list[middle:]) #second page

        print(content2)

        titles = [title + '. Part1', title + '. Part2'] #titles for 2 pages
        content = [content1, content2]

        return titles, content

    return title, content


#function for creating Instant View
def create_instant_view(url):
    telegraph = Telegraph(teletoken)
    too_big = False

    title, content = parse_article(url)

    try:
        response = telegraph.create_page(title=title, html_content=content)
        return response['url']  #url of created telegraph page

    except TelegraphException: #if article is too big
        print("Oh no, something went wrong.")
        titles, contents = parse_article(url, too_big=True)

        response1 = telegraph.create_page(title=titles[0],
                                          html_content=contents[0])
        response2 = telegraph.create_page(title=titles[1],
                                          html_content=contents[1])
        #urls of created telegraph pages
        return [response1['url'], response2['url']]


def parse_news(user_id):
    titles = []
    urls = []
    all_news = {}

    team_name = users_controller.get_user(user_id).team

    url = get_team_foot_url(team_name)

    page = requests.get(url)
    html = page.text

    soup = BeautifulSoup(html, 'lxml')

    news = soup.find('article', class_='news-feed')
    other_news = news.find('ul').find_all('li', attrs={'class':None})[:10]

    for article in other_news:
        titles.append(article.find('a').get_text())
        urls.append(article.find('a')['href'])

    all_news['titles'] = titles
    all_news['urls'] = urls

    return all_news



def get_football_link(name):
    url = 'http://football.ua/default.aspx?menu_id=search_team&search={}'.format(name)
    page = requests.get(url)
    html = page.text

    soup = BeautifulSoup(html, 'lxml')
    link = soup.find('div', class_='clubs').find('div', class_='result-block').find('div', class_='text').find('a')['href']

    return link


def parse_teams():
    teams_dict = {}
    url = 'https://2018.football.ua'
    page = requests.get(url + '/teams')
    html = page.text

    soup = BeautifulSoup(html, 'lxml')

    teams = soup.find('ul', class_="news-list three-columns-list teams-list-page clearfix").find_all('li')

    for team in teams:
        team_name = team.find('h2', class_='news-title').text
        foot_link = get_football_link(team_name)
        champ_link = url + team.find('a', class_='news-link')['href']

        link_dict = {
                    'foot_link': foot_link,
                    'champ_link': champ_link
                   }

        teams_dict[team_name] = link_dict

    with open('footlinks.json', 'w') as file:
        json.dump(teams_dict, file, indent=4, ensure_ascii=False)

    return sorted([team for team in teams_dict])


def get_teams_list():
    teams_list = []
    try:
        with open('footlinks.json', 'r') as file:
            data = json.load(file)
            teams_list = sorted([team for team in data])
    except FileNotFoundError:
        teams_list = parse_teams()

    return teams_list


def get_teams_squad(user_id):
    team_name = users_controller.get_user(user_id).team
    url = get_team_foot_url(team_name)
    countries_dict = get_countries_dict()

    message_text = ''
    squad_positions = ['*Вратари:\n*', '*Защитники:\n*', '*Полузащитники:\n*', '*Нападающие:\n*']

    page = requests.get(url)
    html = page.text

    soup = BeautifulSoup(html, 'lxml')

    squad_block = soup.find('article', class_='team-consist')


    for i, position_table in enumerate(squad_block.find_all('table', class_='consist-table')):
        message_text += squad_positions[i]

        footballers = position_table.find_all('tr')
        country_emoji = ''

        for footballer in footballers:
            num = footballer.find('td', class_='num').get_text()
            name = footballer.find('a').get_text()
            try:
                birth_date = footballer.find('td', class_='birth').find('p').get_text()
            except:
                birth_date = 'не указано'
                print('Birth date uknown')
            country_name = footballer.find('img')['alt']

            for key in countries_dict:
                if countries_dict[key] == country_name:
                    country_code = key
                    country_emoji = flag.flagize(':{}:'.format(country_code))

            message_text += '{}. {} {} (_{}_)\n'.format(num, country_emoji, name, birth_date)
        message_text += '\n'

    return message_text
