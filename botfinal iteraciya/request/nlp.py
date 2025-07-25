import re
import random
import logging
from logging.handlers import RotatingFileHandler
import spacy
from fuzzywuzzy import fuzz
from difflib import get_close_matches
import sqlite3
from pathlib import Path

# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = RotatingFileHandler('bot.log', maxBytes=5*1024*1024, backupCount=5)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Логирование нераспознанных запросов
unrecognized_handler = RotatingFileHandler('unrecognized.log', maxBytes=5*1024*1024, backupCount=5)
unrecognized_handler.setLevel(logging.INFO)
unrecognized_handler.setFormatter(formatter)
logger.addHandler(unrecognized_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class NLPProcessor:
    def __init__(self):
        logging.info("Initializing NLPProcessor")
        try:
            # Проверка наличия модели
            if not spacy.util.is_package("ru_core_news_sm"):
                logging.error("Model 'ru_core_news_sm' not found. Please run 'python -m spacy download ru_core_news_sm'")
                raise ImportError("Model 'ru_core_news_sm' not found")
            self.nlp = spacy.load("ru_core_news_sm")
            logging.info("SpaCy model 'ru_core_news_sm' loaded successfully")
            self._init_db()
            self._init_typo_dictionary()
            self._init_knowledge_base()
            logging.debug("Knowledge base, typo dictionary, and database initialized")
        except Exception as e:
            logging.error(f"Initialization error: {e}", exc_info=True)
            raise

    def _init_db(self):
        #Инициализация базы данных для хранения новых слов и ошибок
        logging.debug("Initializing SQLite database")
        try:
            self.db_path = Path("typo_database.db")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS typos (
                    correct_word TEXT,
                    typo TEXT,
                    frequency INTEGER DEFAULT 1,
                    PRIMARY KEY (correct_word, typo)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS unrecognized_queries (
                    query TEXT,
                    frequency INTEGER DEFAULT 1,
                    PRIMARY KEY (query)
                )
            ''')
            conn.commit()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logging.info(f"Tables in database: {tables}")
            cursor.execute("SELECT correct_word, typo, frequency FROM typos")
            typos = cursor.fetchall()
            logging.debug(f"Typos in database: {typos}")
            conn.close()
            logging.info("SQLite database initialized")
        except Exception as e:
            logging.error(f"Database initialization error: {e}", exc_info=True)

    def _add_typo_to_db(self, correct_word, typo):
        #Добавление нового ошибочного написания в базу данных
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO typos (correct_word, typo, frequency)
                VALUES (?, ?, COALESCE((SELECT frequency + 1 FROM typos WHERE correct_word = ? AND typo = ?), 1))
            ''', (correct_word, typo, correct_word, typo))
            conn.commit()
            conn.close()
            logging.debug(f"Added typo '{typo}' for '{correct_word}' to database")
        except Exception as e:
            logging.error(f"Error adding typo to database: {e}", exc_info=True)

    def _add_unrecognized_query_to_db(self, query):
        #Добавление нераспознанного запроса в базу данных#
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO unrecognized_queries (query, frequency)
                VALUES (?, COALESCE((SELECT frequency + 1 FROM unrecognized_queries WHERE query = ?), 1))
            ''', (query, query))
            conn.commit()
            conn.close()
            logging.debug(f"Added unrecognized query '{query}' to database")
        except Exception as e:
            logging.error(f"Error adding unrecognized query to database: {e}", exc_info=True)

    def _init_typo_dictionary(self):
        #Инициализация словаря частых ошибок
        logging.debug("Initializing typo dictionary")
        self.typo_dictionary = {
            "привет": ["прифет", "приветт", "приветик", "привт"],
            "видеонаблюдение": ["видионаблюдение", "видео наблюдение", "виденаблюдение", "видио наблюдение"],
            "камера": ["комера", "камерра", "кмера"],
            "телефония": ["телифония", "телефони", "телифоня"],
            "ip телефония": ["ип телефония", "ip тилифония", "айпи телефония"],
            "iptv": ["иптв", "ip tv", "айпитиви", "ип тв"],
            "телевизор": ["тиливизор", "теливзор", "телевизир"],
            "интернет": ["интеренет", "интрнет", "интернетт", "инетрнет","интернетик"],
            "настройка": ["настрокйа", "настройк", "настроика"],
            "подключение": ["подключенние", "подключние", "подклюение"],
            "тариф": ["тариффы", "тарифи", "тариф", "тарифы"],
            "качество": ["качесттво", "качство", "качетво"],
            "сигнал": ["сигнл", "сгнал", "сигналл"],
        }
        try:
            if hasattr(self, 'db_path'):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT correct_word, typo FROM typos")
                for correct_word, typo in cursor.fetchall():
                    if correct_word in self.typo_dictionary:
                        self.typo_dictionary[correct_word].append(typo)
                    else:
                        self.typo_dictionary[correct_word] = [typo]
                conn.close()
                logging.debug("Typo dictionary loaded from database")
            else:
                logging.warning("db_path not initialized, skipping typo dictionary load from database")
        except Exception as e:
            logging.error(f"Error loading typos from database: {e}", exc_info=True)

    def _init_knowledge_base(self):
        #Инициализация базы знаний с регулярными выражениями и ключевыми словами
        #её же можно расширять по базе данных с запросами.
        logging.debug("Initializing knowledge base")
        self.knowledge_base = [
            {
                "patterns": [
                    r"(привет|здравствуй|добрый|хай|приветствую|здаров|hi|hello|здрасте|приветствую)",
                    r"(.*)привет(.*)",
                    r"(.*)здравствуй(.*)",
                    r"(.*)приветствую(.*)"
                ],
                "keywords": ["привет", "здравствуй", "добрый", "прифет"],
                "responses": [
                    "Здравствуйте! Чем могу помочь?",
                    "Привет! Как я могу вам помочь сегодня?",
                    "Добрый день! Задавайте ваш вопрос."
                ]
            },
            {
                "patterns": [
                    r"(.*)график(.*)Александров(.*)",
                    r"(.*)работает(.*)офис(.*)Александров(.*)",
                    r"(.*)время(.*)Александров(.*)"
                ],
                "keywords": ["график", "александров","работы", "время", "офис", "Александров"],
                "responses": [
                    "График работы офиса в г. Александров: пн-пт с 9:00 до 19:00, выходные с 10:00 до 17:00"
                ]
            },
            {
                "patterns": [
                    r"(.*)график(.*)офис(.*)Карабаново(.*)",
                    r"(.*)график(.*)Карабаново(.*)",
                    r"(.*)время(.*)офис(.*)Карабаново(.*)",
                    r"(.*)работает(.*)офис(.*)Карабаново(.*)",
                    r"(.*)время(.*)Карабаново(.*)"
                ],
                "keywords": ["график", "Карабаново","работы", "время", "офис"],
                "responses": [
                    "График работы офиса в г. Карабаново: вт-пт с 9:00 до 18:00, суб с 10:00 до 17:00, вс-пн выходной"
                ]
            },
            { 
                "patterns":[
                    r"(график\sработы\sофиса)"
                ],
                "keywords": ["график","работы","офиса","офисов"],
                "responses":[
                    "Для уточнения графика работы офиса. напишите какой офис конкретно интересует\n В формате 'График работы офиса Александров'"
                ]

            },
            {
                "patterns": [
                    r"(.*)график(.*)офис(.*)Струнино(.*)",
                    r"(.*)график(.*)Струнино(.*)",
                    r"(.*)время(.*)офис(.*)Струнино(.*)",
                    r"(.*)графикСтрунино(.*)",
                    r"(.*)работает(.*)офис(.*)Струнино(.*)",
                    r"(.*)время(.*)Струнино(.*)"
                ],
                "keywords": ["график", "Струнино", "время", "офис"],
                "responses": [
                    "График работы офиса в г. Струнино: вт-пт с 9:00 до 18:00, суб с 10:00 до 17:00, вс-пн выходной"
                ]
            },
            {
                "patterns": [
                    r"(сколько|когда|как)видеонаблюдение(.*)"
                ],
                "keywords": ["видеонаблюдение","сколько","когда","как"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о услуге видеонаблюдении? \nДля консультации по вопросам видеонаблюдения \nможете связаться с нами по телефону 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(сколько|когда|как)(.*)интернет(.*)"
                ],
                "keywords": ["интернет","сколько","когда","как"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о услуге интернет? \nДля консультации по вопросам интернета \nможете связаться с нами по телефону 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(сколько|когда|как)(.*)телевидение(.*)"
                ],
                "keywords": ["телевидение","сколько","когда","как"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о услуге телевидение? \nДля консультации по вопросам интернета \nможете связаться с нами по телефону 3-33-00"
                ]
            },
               {
                "patterns": [
                    r"(IPTV|ip-tv|интернет)(.*) телевидение(.*)"
                ],
                "keywords": ["IPTV","ip-tv","интернет телевидение"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о услуге интернет телевидения? \nДля консультации по вопросам интернета \nможете связаться с нами по телефону 3-33-00"
                ]
            },
               {
                "patterns": [
                    r"Телевидение"
                ],
                "keywords": ["телевидение"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о видеонаблюдении? \nДля консультации по вопросам интернета \nможете связаться с нами по телефону 3-33-00"
                ]
            },
               {
                "patterns": [
                    r"Телевидение"
                ],
                "keywords": ["телевидение"],
                "responses": [
                    "Вы бы хотели узнать что-то конкретное о видеонаблюдении? \nДля консультации по вопросам интернета \nможете связаться с нами по телефону 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)стоимость(.*)подключения",
                    r"(.*)подключение(.*)"
                ],
                "keywords": ["стоимость", "подключение"],
                "responses": [
                    "Стоимость подключения зависит от адреса. Для консультации звоните по телефону 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(помоги)(.*)",
                    r"(.*)(помогите)(.*)",
                    r"(.*)(техническая\sподдержка|техподдержка|тех\sподдержка|помощь)(.*)",
                    r"(не\sработает|не\sвключается|сломался|глючит|не\sоткрывает)(.*)",
                    r"(.*)(проблема|ошибка)(.*)(сайт|ошибка)"
                ],
                "keywords": ["техподдержка", "проблема", "ошибка", "не работает", "помогите"],
                "responses": [
                    "Пожалуйста опишите проблему более подробно в формате:\n1. Адрес\n2. Характер проблемы\n3. Устройство на котором проблема проявляется"
                ]
            },
            {
                "patterns": [
                    r"(.*)(не\sработает|не\sдоступен|не\sгрузит|не\sзагружает|не\sоткрывается)(.*)(сайт|ресурс|страница|портал)(.*)",
                    r"(.*)(сайт|ресурс)(.*)(не\sгрузится|не\sоткрывается|не\sдоступен)(.*)",
                    r"(.*)(проблема|ошибка)(.*)(доступ\sк\sсайту|загрузка\sстраницы)",
                    r"(.*)(не\sмож(ет|гу))(.*)(зайти|перейти|открыть)(.*)(сайт|ресурс)"
                ],
                "keywords": ["сайт", "не грузится", "ошибка"],
                "responses": [
                    "При проблемах с доступом к сайтам:\n1. Проверьте интернет-соединение\n2. Попробуйте другой браузер\n3. Очистите кэш браузера\n4. Звоните в поддержку по 3-33-00",
                    "Если сайт не доступен:\n- Проверьте работу других сайтов\n- Попробуйте через мобильный интернет\n- Возможно, ведутся технические работы"
                ]
            },
            {
                "patterns": [
                    r"(.*)(контакты|телефон|как\sсвязаться)(.*)",
                    r"(.*)(позвонить|написать)(.*)",
                    r"(.*)где\sнаходитесь(.*)"
                ],
                "keywords": ["контакты", "телефон", "адрес"],
                "responses": [
                    "Контакты:\n📞 Телефон: 8-492-443-33-00\n📍 Адрес: г. Александров, ул. Октябрьская д.8, 1",
                    "Связаться с нами: телефон 3-33-00 или онлайн-чат на сайте"
                ]
            },
            {
                "patterns": [
                    r"(.*)(нет\sинтернетsа|не\sработает)(.*)",
                    r"(.*)(медленный\sинтернет|тормозит\sинтернет)(.*)",
                    r"(.*)(пропал\sинтернет)(.*)"
                ],
                "keywords": ["интернет",  "медленный","не работает"],
                "responses": [
                    "При проблемах с интернетом:\n1. Перезагрузите роутер\n2. Проверьте кабели\n3. Звоните в поддержку по 3-33-00"
                ]
            },
             {
                "patterns": [
                    r"(.*)(низкая скорость| слабый интернет)(.*)",
                    r"(.*) (плохо),(работает интернет)(.*)"
                ],
                "keywords": ["плохо работает", "низкая", "скорость", "слабый", "интернет"],
                "responses": [
                    "При проблемах со скоростью при подключении:\n1.Убедитесь что вы подключены к Wi-Fi \n2. Замерьте скорость посредством использования https://www.speedtest.net/ \n3. Свяжитесь с нами Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(не\sработает|не\sвключается|глючит)(.*)(телефон|смартфон|андроид)",
                    r"(проблема|ошибка)(.*)(телефон|смартфон)"
                ],
                "keywords": ["телефон", "смартфон" ],
                "responses": [
                    "Попробуйте:\n1. Перезагрузить устройство\n2. Проверить настройки сети\n3. Обновить ПО",
                    "Для проблем с телефоном проверьте:\n- Заряд батареи\n- Режим полета\n- SIM-карту"
                ]
            },
            {
                "patterns": [
                    r"(.*)(не\sгорит|не\sгорят|лампочка|лампочки)(.*)(не\sработает|не\sвключается|сломалась)",
                    r"(.*)(лампочка|лампочки)(.*)(гаснет|не\sсветит)"
                ],
                "keywords": ["лампочка", "не горит"],
                "responses": [
                    "Если лампочки не горят:\n1. Проверьте подключение роутера\n2. Убедитесь, что питание включено\n3. Обратитесь в поддержку по 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(не\sработает|не\sвключается|глючит|не\sпоказывает)(.*)(камера|видеокамера|видеонаблюдение)"
                ],
                "keywords": ["видеонаблюдение", "камера", "настройка", "качество", "записи", "поворачивается", "зависает", "не фокусируется", "фокусируется"],
                "responses": [
                    "Если видеонаблюдение не работает:\n1. Проверьте подключение камеры\n2. Убедитесь, что приложение обновлено\n3. Перезагрузите устройство\n4. Звоните в поддержку по 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(не\sзаписывает)(.*)(видео|камера|звук)(.*)"
                ],
                "keywords": ["камера", "звук"],
                "responses": [
                    "Если камера перестала записывать звук:\n1. Перезагрузите выключив инжектор (её питание) из розетки\n2. Свяжитесь с нами по номеру 3-33-00 для консультации и диагностики"
                ]
            },
            {
                "patterns": [
                    r"(.*)(не\sвидно|плохое\sкачество|)(.*)(камере|архиве)(.*)"
                ],
                "keywords": ["не видно", "плохое качество", "объектив", " картинка"],
                "responses": [
                    "Если камера не фокусируется:\n1. Уточните чиста ли линза самой камеры\n2. Очистите объектив\n3. Звоните в поддержку по 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(нет\sдоступа)(.*)(архив)(.*)"
                ],
                "keywords": ["нет доступа", "архив", "приложение мои камеры"],
                "responses": [
                    "Для доступа к записям видеонаблюдения:\n1. Используйте личный кабинет видеонаблюдения\n2. Убедитесь, что подписка активна\n3. Звоните в поддержку по 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(iptv\sне\sпоказывает\sканалы|черный\sэкран\sна\sтв)(.*)"
                ],
                "keywords": ["iptv", "черный экран","IPTV","иптв","телевизор"],
                "responses": [
                    "При проблемах с IPTV:\n1. Нажмите 'Источник' на пульте → выберите HDMI\n2. Перезагрузите приставку (отключите на 10 сек)\n3. Проверьте кабель HDMI на повреждения"
                ]
            },
            {
                "patterns": [
                    r"(.*)(iptv\sмедленно\sпереключает\sканалы|лагает\sпри\sсмене\sканала)(.*)"
                ],
                "keywords": ["медленно", "переключение"],
                "responses": [
                    "Решение для медленного переключения:\n1. Проверьте скорость интернета (минимум 15 Мбит/с)\n2. В настройках включите 'Буферизацию'\n3. Обновите плейлист через 'Система → Обновление'"
                ]
            },
            {
                "patterns": [
                    r"(.*)(ip\sтелефон\sне\sрегистрируется|ошибка\svoip)(.*)"
                ],
                "keywords": ["телефония", "не регистрируется"],
                "responses": [
                    "При проблемах с регистрацией:\n1. Проверьте SIP-данные в разделе 'Телефония' ЛК\n2. Убедитесь, что телефон подключен к LAN-порту\n3. Для офисных АТС - проверьте VLAN"
                ]
            },
            {
                "patterns": [
                    r"(.*)(пропадает\sзвук\sв\sip\sтелефонии|прерывается\sразговор)(.*)"
                ],
                "keywords": ["звук", "прерывается"],
                "responses": [
                    "Если пропадает звук:\n1. Проверьте стабильность интернет-соединения\n2. Обновите прошивку телефона\n3. Настройте QoS на роутере для VoIP"
                ]
            },
            {
                "patterns": [
                    r"(.*)(жалоба|недоволен|плохой\sсервис)(.*)"
                ],
                "keywords": ["жалоба", "плохой сервис", "грубость"],
                "responses": [
                    "Сожалеем о неудобствах! Опишите проблему, и мы решим её:\n1. Укажите суть проблемы\n2. Сообщите время инцидента\n3. Звоните в поддержку по 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(оплата|платеж)(.*)(интернет|видеонаблюдение|телефония|iptv|иптв)(.*)",
                    r"(.*)(как\sоплатить)(.*)(интернет|видеонаблюдение|телефония|iptv|иптв)(.*)",
                    r"(.*)(как\sоплатить)(.*)"
                ],
                "keywords": ["оплата","услуга", "видеонаблюдение", "телефония", "iptv","оплатить"],
                "responses": [
                    "Оплатить услуги видеонаблюдения, IP-телефонии или IPTV можно через личный кабинет, приложение банка или в офисе",
                    "Способы оплаты: онлайн в личном кабинете, в офисе, через банковское приложение. Для деталей звоните 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(ip\sтелефон\sне\sзвонит|не\sпроходят\sисходящие\sвызовы)(.*)",
                    r"(.*)(не\sработает\sисходящая\sсвязь\sна\sip\sтелефонии)(.*)"
                ],
                "keywords": ["не звонит", "исходящие вызовы"],
                "responses": [
                    "Если не работают исходящие вызовы:\n1. Проверьте баланс SIP-аккаунта в личном кабинете\n2. Убедитесь, что номер не в черном списке\n3. Проверьте настройки исходящего маршрута (Outbound Route)\n4. Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(нет\sзвука\sв\sip\sтелефонии|не\sслышно\sсобеседника)(.*)",
                    r"(.*)(абонент\sне\sслышит\sменя\sпри\sразговоре)(.*)"
                ],
                "keywords": ["нет звука", "не слышно"],
                "responses": [
                    "При проблемах со звуком:\n1. Проверьте громкость динамика/микрофона на устройстве\n2. Убедитесь, что в настройках кодеков выбран G.711 или G.729\n3. Проверьте NAT-трансляцию на роутере\n4. Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(ip\sтелефон\sне\sрегистрируется\sна\sсервере)(.*)",
                    r"(.*)(ошибка\sрегистрации\svoip\sустройства)(.*)"
                ],
                "keywords": ["не регистрируется", "ошибка регистрации"],
                "responses": [
                    "При проблемах с регистрацией:\n1. Проверьте логин/пароль SIP (раздел 'Телефония' в ЛК)\n2. Убедитесь, что устройство подключено к интернету\n3. Проверьте настройки прокси-сервера (должен быть ваш VoIP-провайдер)\n4. Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(звонки\sпрерываются\sчерез\sN\sсекунд)(.*)",
                    r"(.*)(разговор\sобрывается\sчерез\sнекоторое\sвремя)(.*)"
                ],
                "keywords": ["прерывается", "обрывается"],
                "responses": [
                    "Если звонки прерываются:\n1. Проверьте стабильность интернет-соединения (ping < 100ms)\n2. Настройте QoS для VoIP-трафика на роутере\n3. Уменьшите интервал keepalive до 20 сек\n4. Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(эхо\sв\sip\sтелефонии|слышу\sсвой\sголос)(.*)"
                ],
                "keywords": ["эхо", "свой голос","себя"],
                "responses": [
                    "При проблемах с эхом:\n1. Уменьшите громкость динамика на устройстве\n2. Используйте гарнитуру вместо громкой связи\n3. Включите подавление эха в настройках телефона\n4. Техподдержка: 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(как\sнастроить\sip\sтелефон\sвпервые)(.*)",
                    r"(.*)(первоначальная\sнастройка\svoip)(.*)"
                ],
                "keywords": ["настроить", "первоначальная настройка"],
                "responses": [
                    "Первоначальная настройка IP-телефона:\n1. Введите SIP-логин/пароль из личного кабинета\n2. Укажите сервер регистрации: voip.provider.ru\n3. Выберите кодек G.711 или G.729\n4. Для помощи звоните 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(тарифы)(.*)",
                    r"(.*)(акции)(.*)"
                ],
                "keywords": ["тариф", "стоимость", "акции"],
                "responses": [
                    "Актуальную информацию по тарифам и акциям:\n1. Смотрите в личном кабинете в разделе 'Телефония'\n2. Или уточните у оператора по телефону 3-33-00\n3. Текущие акции: бесплатные междугородние звонки по выходным"
                ]
            },
            {
                "patterns": [
                    r"(.*)(стоимость|цена|сколько\sстоит)(.*)(видеонаблюдение|телефония|iptv|иптв)",
                    r"(.*)(подключение|установка)(.*)(видеонаблюдение|телефония|iptv|иптв)"
                ],
                "keywords": ["стоимость", "видеонаблюдение", "телефония", "iptv", "подключение"],
                "responses": [
                    "Стоимость подключения видеонаблюдения, IP-телефонии или IPTV зависит от тарифа и адреса. Для консультации звоните по телефону 3-33-00",
                    "Для уточнения цены на установку услуг обратитесь в офис или позвоните по номеру 3-33-00"
                ]
            },
            {
                "patterns": [
                    r"(.*)(проконсультируйте)(.*)",
                    r"(.*)(консультация)(.*)"
                ],
                "keywords": [],
                "responses": [
                    "Извините, я не понял. Можете переформулировать? Например, спросите про интернет, видеонаблюдение, IP-телефонию или IPTV.",
                    "Уточните, пожалуйста, ваш вопрос. Я не понял о чем вы."
                ]
            },
            {
                "patterns": [r".*"],
                "keywords": [],
                "responses": [
                    "Извините, я не понял. Можете переформулировать? Например, спросите про интернет, видеонаблюдение, IP-телефонию или IPTV.",
                    "Уточните, пожалуйста, ваш вопрос. Я не понял о чем вы."
                ]
            }
        ]

    def preprocess_text(self, text):
        # предобработка текста с использованием spaCy
        logging.debug(f"Preprocessing text: {text}")
        try:
            # Удаляем лишние символы и приводим к нижнему регистру
            text = re.sub(r'[^\w\s]', '', text.lower())
            doc = self.nlp(text)
            # Лемматизация и удаление стоп-слов
            tokens = [token.lemma_ for token in doc if not token.is_stop and len(token.text) > 2]
            return tokens
        except Exception as e:
            logging.error(f"Text preprocessing error: {e}", exc_info=True)
            return []

    def _correct_spelling(self, token, dictionary):
        #Исправление опечаток с использованием fuzzywuzzy и get_close_matches
        try:
            # Проверяем словарь частых ошибок
            for correct_word, typos in self.typo_dictionary.items():
                if token in typos:
                    logging.debug(f"Corrected '{token}' to '{correct_word}' using typo dictionary")
                    return correct_word
            # Проверяем схожесть с известными словами
            matches = get_close_matches(token, dictionary, n=1, cutoff=0.5)
            if matches:
                logging.debug(f"Corrected '{token}' to '{matches[0]}' using get_close_matches")
                self._add_typo_to_db(matches[0], token)
                return matches[0]
            # Дополнительная проверка с fuzzywuzzy
            best_match = None
            best_score = 0
            for word in dictionary:
                score = fuzz.ratio(token, word)
                if score > 50 and score > best_score:  # Пониженный порог
                    best_match = word
                    best_score = score
            if best_match:
                logging.debug(f"Corrected '{token}' to '{best_match}' using fuzzywuzzy (score: {best_score})")
                self._add_typo_to_db(best_match, token)
                return best_match
            # Логируем нераспознанное слово
            logging.info(f"Unrecognized token: '{token}'", extra={'logger_name': 'unrecognized'})
            return token
        except Exception as e:
            logging.error(f"Spelling correction error for '{token}': {e}", exc_info=True)
            return token

    def _match_pattern_score(self, text, pattern, keywords):
        #Оценивает, насколько запрос соответствует шаблону (от 0 до 1).
        try:
            # Проверка по регулярному выражению
            if re.fullmatch(pattern, text, re.IGNORECASE):
                return 1.0  # Полное совпадение
            # Лемматизация и проверка ключевых слов
            tokens = self.preprocess_text(text)
            # Используем общий словарь для исправления опечаток, а не только keywords текущей категории
            all_keywords = set(kw for cat in self.knowledge_base for kw in cat.get("keywords", []))
            dictionary = all_keywords if all_keywords else set(keywords)
            corrected_tokens = [self._correct_spelling(token, dictionary) for token in tokens]
            # Оценка на основе количества совпавших ключевых слов
            stemmed_keywords = [self.nlp(keyword)[0].lemma_ for keyword in keywords]
            matched_keywords = sum(1 for kw in stemmed_keywords if kw in corrected_tokens) # Исправлена опечатка: atched -> matched
            # Добавлена проверка деления на ноль
            keyword_count = len(keywords)
            if keyword_count == 0:
                 return 0.5 # Или другое значение по умолчанию для категорий без ключевых слов
            return min(1.0, matched_keywords / keyword_count) # Добавлена закрывающая скобка
        except Exception as e:
            logging.error(f"Scoring error for pattern '{pattern}': {e}", exc_info=True)
            return 0.0

    def get_response(self, text):
        best_match = None
        best_score = 0
        for category in self.knowledge_base:
            for pattern in category["patterns"]:
                match_score = self._match_pattern_score(text, pattern, category["keywords"])
                if match_score > best_score:
                    best_score = match_score
                    best_match = category
        if best_match and best_score > 0.7:  # Порог уверенности
            return random.choice(best_match["responses"])
        else:
            # Логируем нераспознанный запрос
            self._add_unrecognized_query_to_db(text)
            return "Извините, я не понял. Уточните вопрос?"

