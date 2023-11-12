Foodgram - социальная сеть рецептов, доступна по адресу:
http://158.160.24.76/
https://vasmalfoodgram.hopto.org

Email vasiliy.malyshev@hmail.com
Пароль DfcbkbqYbyf

Технологии:
Django
Python
Docker
Запуск проекта:
Клонируйте проект:
git clone git@github.com:malyshevvasiliy/foodgram-project-react.git

Подготовьте сервер:
scp docker-compose.yml <username>@<host>:/home/<username>/
scp nginx.conf <username>@<host>:/home/<username>/
scp .env <username>@<host>:/home/<username>/

Установите docker и docker-compose:
sudo apt install docker.io 
sudo apt install docker-compose
Соберите контейнер и выполните миграции:
sudo docker-compose up -d --build
sudo docker-compose exec backend python manage.py migrate
Создайте суперюзера и соберите статику:
sudo docker-compose exec backend python manage.py createsuperuser
sudo docker-compose exec backend python manage.py collectstatic --no-input
