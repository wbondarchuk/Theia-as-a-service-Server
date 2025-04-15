import os
from subprocess import Popen, PIPE
from flask import current_app
from flask_login import current_user
import socket
from contextlib import closing
from .models import Container, User
from . import db
from project.config import HOST, DOCKER_IMAGE, DOCKER_NEW_CLIENT_OUTPUT_SUBSTR, DOCKER_CLIENT_EXITED_OUTPUT_SUBSTR, DOCKER_EXPOSED_PORT, MIN_PORT, MAX_PORT

# запускает команду в shell и возвращает вывод
def run_cmd(cmd):
    process = Popen(cmd, stdout=PIPE, shell=True)
    return process.communicate()[0].decode('utf-8')


# запускает контейнер на случайном порту и возвращает вывод
def start_container(id):
    """Запускает контейнер на предопределённом порту (без проверки доступности порта)"""
    result = run_cmd(f'docker start {id}')
    current_app.logger.info(f'Started container {result[:-1]}')
    return result


def create_container():
    """Создаёт контейнер на следующем доступном порту из диапазона"""
    try:
        port = find_available_port()
        id = run_cmd(f'docker create --publish {port}:{DOCKER_EXPOSED_PORT} {DOCKER_IMAGE}')[:12]
        name = run_cmd('docker ps -a --filter "id=' + id + '" --format "{{.Names}}"')[:-1]

        new_container = Container(
            id=id,
            user_id=current_user.id,
            container_name=name,
            port=port
        )
        db.session.add(new_container)
        db.session.commit()

        username = current_user.name
        # Создаем конфиг Nginx
        create_nginx_config(username, name, port)

        current_app.logger.info(f'Created container {name} ({id}) on port {port}')
        return id
    except Exception as e:
        db.session.rollback()
        raise Exception("No available ports in the specified range. Please try again later.")


def create_nginx_config(username, container_name, port):
    """Создаёт конфигурацию Nginx с учётом имени пользователя"""
    config = f"""
    location /{username}/{container_name}/ {{
        proxy_pass http://{HOST}:{port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_redirect off;
        proxy_buffering off;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        rewrite ^/{username}/{container_name}/(.*)$ /$1 break;
    }}
    """

    # Создаем директорию для конфигов, если её нет
    os.makedirs('/etc/nginx/containers', exist_ok=True)

    # Записываем конфиг в отдельный файл
    config_path = f'/etc/nginx/containers/{username}_{container_name}.conf'
    with open(config_path, 'w') as f:
        f.write(config)

    # Перезагружаем Nginx
    try:
        run_cmd("nginx -t")  # Сначала проверяем конфигурацию
        run_cmd("nginx -s reload")
        current_app.logger.info(f"Nginx configuration for {container_name} reloaded successfully")
    except Exception as e:
        current_app.logger.error(f"Failed to reload Nginx: {str(e)}")
        raise Exception(f"Nginx reload failed: {str(e)}")

def get_URL(container_id, username):
    """Возвращает URL в формате /username/container_name"""
    container = Container.query.get_or_404(container_id)
    return f'http://{HOST}/{username}/{container.container_name}/'

def is_port_available(port):
    """Проверяет, свободен ли порт"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((HOST, port)) != 0


def find_available_port():
    """Находит свободный порт в заданном диапазоне, учитывая порты из БД"""
    # Получаем все занятые порты из базы данных
    used_ports = {container.port for container in Container.query.all()}

    # Проверяем порты в заданном диапазоне
    for port in range(MIN_PORT, MAX_PORT + 1):
        # Порт свободен, если его нет в БД и он доступен в системе
        if port not in used_ports and is_port_available(port):
            return port
    raise Exception("No available ports in the specified range")


# останавливает контейнер и возвращает вывод команды
def stop_container(id):
    result = run_cmd(f'docker stop {id}')
    current_app.logger.info(f'Stopped container: {result[:-1]}')
    return result


# удаляет контейнер из докера и из БД, возвращает вывод докер команды
def force_remove_container(id):
    container = Container.query.get_or_404(id)
    user = User.query.get(container.user_id)
    container_name = container.container_name
    result = run_cmd(f'docker rm -f {id}')[:-1]
    current_app.logger.info(f'Force removed container: {result}')

    # Удаляем конфиг Nginx
    config_path = f'/etc/nginx/containers/{user.name}_{container_name}.conf'
    if os.path.exists(config_path):
        os.remove(config_path)
        run_cmd("nginx -s reload")

    Container.query.filter_by(id=id).delete()
    db.session.commit()
    current_app.logger.info(f'Deleted container {id} from DB')

    return result


# возвращает число строк в логах контейнера, содержащих подстроку substr
# если вдруг утилита wc вернёт не число, выбросится исключение с выводом wc
def number_of_log_lines(container, substr):
    result = run_cmd(f'''docker logs {container} 2>&1 | grep -n "{substr}" | wc -l''')
    try:
        return int(result)
    except ValueError:
        raise Exception(f'"wc -l" returned: {result}')


# возвращает список айднишников контейнеров
def get_containers():
    return run_cmd(f'docker ps -q --filter "ancestor={DOCKER_IMAGE}"').splitlines()


# останавливает запущенные контейнеры, из которых вышел юзер (или все, если параметр True)
def stop_containers(stop_all = False):
    current_app.logger.info(f'Stopping containers (stop_all={stop_all})...')
    for container in get_containers():
        to_stop = stop_all
        if not to_stop:
            clients_entered = number_of_log_lines(container, DOCKER_NEW_CLIENT_OUTPUT_SUBSTR)
            clients_exited = number_of_log_lines(container, DOCKER_CLIENT_EXITED_OUTPUT_SUBSTR)
            current_app.logger.info(f'Container {container}: entered {clients_entered}, exited {clients_exited}')
            to_stop = clients_exited >= clients_entered
        if to_stop:
            stop_container(container)
