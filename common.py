import sys
import os
import subprocess
import json
import shutil

ROUTE_FILE_PATH = '/proc/net/route'
UFW_BEFORE_RULES_PATH = '/etc/ufw/before.rules'
SYSCTL_FILE_PATH = '/etc/sysctl.conf'
FORWARD_POLICY_FILE = '/etc/default/ufw'
SSHD_CONFIG_PATH = '/etc/ssh/sshd_config'
ENCODING = 'UTF-8'
RUN_COMMAND_TIMEOUT = 20_000

DEFAULT_SSH_PORT = 22
DEFAULT_NO_UFW = False
DEFAULT_CLIENTS = []
DEFAULT_DNS = ['1.1.1.1', '1.0.0.1']

CHECK_MODE = False
DEFAULT_CLIENTS_DIR = os.path.expanduser('~/.veepeenet/clients')
RESULT_LOG_PATH = os.path.expanduser('~/.veepeenet/result.json')
CONFIG_PATH = os.path.expanduser('~/.veepeenet/config.json')
RESULT = {
    'has_error': False,
    'meta': {
        'interpreter': sys.executable,
        'interpreter_version':
            f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}',
        'run_args': sys.argv
    },
    'actions': []
}


def handle_result(func: callable) -> callable:
    def wrapper(*args, **kwargs) -> any:
        action = {}
        try:
            res = func(*args, **kwargs)
            action.update({'result': str(res)})
        except Exception as ex:
            RESULT['has_error'] = True
            action.update({'error': str(ex)})
            write_text_file(RESULT_LOG_PATH, json.dumps(RESULT, indent=2))
            raise ex
        finally:
            action.update({
                'name': func.__name__,
                'args': str(args),
                'kwargs': str(kwargs)
            })
            RESULT['actions'].append(action)
        return res

    return wrapper


def write_text_file(file_path: str, text: str, mode: int = 0) -> None:
    if CHECK_MODE:
        print(f'{file_path}:\n{text}\n')
        return

    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
    else:
        if mode:
            os.chmod(file_path, mode)
        with open(file_path, 'rt', encoding=ENCODING) as fd:
            if fd.read() == text:
                return

    with open(file_path, 'wt', encoding=ENCODING) as fd:
        fd.write(text)


@handle_result
def run_command(command: str, stdin: str = '') -> tuple:
    if CHECK_MODE:
        command = f'echo "{command}"'
    try:
        run_result = subprocess.run(
            command,
            input=stdin.encode(ENCODING),
            capture_output=True,
            check=True,
            timeout=RUN_COMMAND_TIMEOUT,
            shell=True
        )

        return (run_result.returncode,
                run_result.stdout.decode(ENCODING).strip(),
                run_result.stderr.decode(ENCODING).strip())
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as ex:
        raise ex


@handle_result
def clean_configuration(config_path: str, clients_dir: str) -> None:
    if os.path.exists(config_path):
        os.remove(config_path)
    if os.path.exists(clients_dir):
        shutil.rmtree(clients_dir)


@handle_result
def get_config_value(config: dict, key: str, prefix: str = '') -> any:
    if not prefix and key in config:
        return config[key]
    if prefix in config and key in config[prefix]:
        return config[prefix][key]
    return None


@handle_result
def get_current_host_ip() -> str:
    return run_command('hostname -i')[1]


@handle_result
def get_existing_clients(config: dict) -> list:
    if 'clients' not in config:
        return []
    return config['clients']


@handle_result
def get_new_clients_names(passed_clients_names: list, existing_clients: list) -> list:
    existing_clients_names = [existing_client['name'] for existing_client in existing_clients]
    return list(set(passed_clients_names) - set(existing_clients_names))


@handle_result
def get_clients_after_removing(clients: list, clients_names_to_remove: list) -> list:
    if not clients_names_to_remove:
        return clients
    return [client for client in clients if client['name'] not in clients_names_to_remove]


@handle_result
def dump_config(config: dict) -> str:
    return json.dumps(config, indent=2)


@handle_result
def generate_unique_number(number_range: range, excluded_numbers: list) -> int:
    for i in number_range:
        if i not in excluded_numbers:
            return i
    raise RuntimeError("Generate unique number error")