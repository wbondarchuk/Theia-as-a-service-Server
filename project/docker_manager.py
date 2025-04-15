from subprocess import Popen, PIPE
from flask import current_app
from flask_login import current_user
import socket
from contextlib import closing
from .models import Container
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

        current_app.logger.info(f'Created container {name} ({id}) on port {port}')
        return id
    except Exception as e:
        db.session.rollback()
        raise Exception("No available ports in the specified range. Please try again later.")


def get_URL(container_id, username):
    """Возвращает URL контейнера на основе сохранённого порта"""
    container = Container.query.get_or_404(container_id)
    return f'http://{HOST}:{container.port}'


def get_container_port(container_id):
    """Возвращает порт контейнера из БД (больше не используем docker port)"""
    container = Container.query.get_or_404(container_id)
    return container.port

def is_port_available(port):
    """Проверяет, свободен ли порт"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((HOST, port)) != 0


def find_available_port():
    """Находит свободный порт в заданном диапазоне"""
    for port in range(MIN_PORT, MAX_PORT + 1):
        if is_port_available(port):
            return port
    raise Exception("No available ports in the specified range")


# останавливает контейнер и возвращает вывод команды
def stop_container(id):
    result = run_cmd(f'docker stop {id}')
    current_app.logger.info(f'Stopped container: {result[:-1]}')
    return result


# удаляет контейнер из докера и из БД, возвращает вывод докер команды
def force_remove_container(id):
    result = run_cmd(f'docker rm -f {id}')[:-1]
    current_app.logger.info(f'Force removed container: {result}')
    
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


def update_nginx_config(username, port):
    config = f"""
    location /{username}/ {{
        proxy_pass http://{HOST}:{port}/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    """
    with open("/etc/nginx/conf.d/containers.conf", "a") as f:
        f.write(config)
    run_cmd("nginx -s reload")

