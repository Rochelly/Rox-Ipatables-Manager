
import subprocess
import re
import os
import datetime
import time
import logging


class Firewall_Handler:

    def __init__(self, config_file) -> None:
        self.log_file = config_file["paths_dir"]["log_file_tmp"]
        self.last_checked_file = config_file["paths_dir"]["last_checked_file"]
        self.service_dir = config_file["paths_dir"]["service_rules_path"]
        self.input_file_rules = config_file["paths_dir"]["input_file_rules"]
        self.net_rules_dir = config_file["paths_dir"]["net_rules_path"]
        logging.basicConfig(filename=self.log_file, level=logging.DEBUG)

    # Terminal commands 
    def run_command(self, command):
        print('')
        print('')
        print('')
        print('')
        try:
            args = command.split()
            completed_process = subprocess.run(
                args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True, completed_process.stdout
        except subprocess.CalledProcessError as error:
            return False,  error.stderr

    def run_command_no_out(self, command):
        print('')
        print('')
        print('')
        print('')
        try:
            args = command.split()
            subprocess.run(args, check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            return False

    # chains handler

    def check_chain_exist(self, chain):
        command = "sudo iptables -nL "+chain
        return self.run_command_no_out(command)

    def check_forward_reference(self, target):
        command = "sudo iptables -nL FORWARD --line-numbers"
        success, output = self.run_command(command)
        if not success:
            return False
        target = " " + target + " "
        for line in output.decode().splitlines():
            if target in line:
                rule_num = line.split()[0]
                return rule_num
        return False

    def delete_forward_reference(self, target):
        while self.check_forward_reference(target):
            subprocess.run(['sudo', 'iptables', '-D', 'FORWARD',
                           self.check_forward_reference(target)])

    def delete_chain(self, chain):
        if not chain:
            return
        self.delete_forward_reference(chain)
        commandF = "sudo iptables -F "+chain
        commandX = "sudo iptables -X "+chain
        self.run_command_no_out(commandF)
        self.run_command_no_out(commandX)

    def create_chain_destination_in_forward(self, chain, ip):

        self.delete_chain(chain)
        command = "sudo iptables -N "+chain
        self.run_command(command)
        referenceChain = "sudo iptables -t filter -I FORWARD -d "+ip+" -j "+chain
        self.run_command(referenceChain)

    def create_chain_soucer_in_forward(self, chain, ip):
        self.delete_chain(chain)
        command = "sudo iptables -N "+chain
        self.run_command(command)
        referenceChain = "sudo iptables -t filter -I FORWARD -s "+ip+" -j "+chain
        self.run_command(referenceChain)

    def remove_Chain_Deleted(self, dir_Path):
        listDeletedFiles = self.check_deleted_files(dir_Path)
        for fileName in listDeletedFiles:
            name = fileName.split('=')
            chain = name[1].strip()
            self.delete_chain(chain)

    # rules create

    def split_port_10(self, ports):
        substrings = ports.split(",")
        sublists = []
        temp = []

        for s in substrings:

            temp.append(s)
            if len(temp) == 10:
                sublists.append(",".join(temp))
                temp = []

        if len(temp) > 0:
            sublists.append(",".join(temp))
        return sublists

    def get_rule_parameters(self, line, parameter):
        value = re.search(rf'{parameter}=([^\s]+)', line)

        if value:
            return value.group(1)
        else:
            return False

    def create_rules(self, chain, source, destination, protocol, ports, action):
        # retorna uma lista de regras  a partir uma linha extraida do arquivo
        rules = []

        if not (source or destination or protocol or ports):
            return rules

        if source and source != '*':
            source = f' -s {source} '
        else:
            source = ''

        if destination and destination != '*':
            destination = f' -d {destination} '
        else:
            destination = ''

        if protocol and protocol != '*':
            protocol = f' -p {protocol} '
        else:
            protocol = ''

        if action and action != '*':
            action = f'-j {action}'
        else:
            action = ' -j ACCEPT'

        if ports and ports != '*':
            ports_list = self.split_port_10(ports)

            for port_group in ports_list:
                ports_cmd = f'-m multiport --dport {port_group}'
                rule_cmd = f"sudo iptables -t filter -A {chain} {source} {destination} {protocol} {ports_cmd} {action}"
                rules.append(rule_cmd)
        else:
            rule_cmd = f"sudo iptables -t filter -A {chain} {source} {destination} {protocol} {action}"
            rules.append(rule_cmd)

        return rules

    def extract_filter_rules_from_file(self, file_name, chain):

        rules_list = []
        lines_list = []

        with open(file_name, 'r') as file:
            for line_num, line in enumerate(file.readlines()):
                # Ignora as linhas de comentário
                if line.startswith('#') or line.startswith('\n'):
                    continue

                source = self.get_rule_parameters(line, 'sourcer')
                destination = self.get_rule_parameters(line, 'destination')
                protocol = self.get_rule_parameters(line, 'protocol')
                action = self.get_rule_parameters(line, 'action')
                ports = self.get_rule_parameters(line, 'ports')

                rules = self.create_rules(
                    chain, source, destination, protocol, ports, action)

                for rule in rules:
                    rules_list.append(rule)
                    lines_list.append(line_num+1)

        print(lines_list, rules_list)
        time.sleep(5)
        return lines_list, rules_list

    def aply_rules_from_file(self, file_name, chain):
        lines, rules = self.extract_filter_rules_from_file(file_name, chain)
        line_rules = list(zip(lines, rules))
        erros = []
        for line, rule in line_rules:
            sucesso, msg = self.run_command(rule)
            if not sucesso:
                erros.append(f"Erro na linha:  {line + 1} do arquivo")
        return erros

    # file handler

    def get_in_file(self, fileName, key):
        with open(fileName) as arquivo:
            value = ''
            for linha in arquivo:
                if linha.startswith(f'{key}='):
                    value = linha.strip().split('=')[1]
                    break
        return value

    def write_files(self, lista_strings, nome_arquivo):
        with open(nome_arquivo, 'w') as arquivo:
            for linha in lista_strings:
                arquivo.write(linha + '\n')

    def get_key_in_file(self, file_name, key):
        with open(file_name) as file:
            value = ''
            for line in file:
                if line.startswith(f'{key}='):
                    value = line.strip().split('=')[1]
                    break
        return value

    def compare_files(self, ald, new):
        with open(ald, 'r') as f1, open(new, 'r') as f2:
            linhas1 = set(f1.readlines())
            linhas2 = set(f2.readlines())
            linhas_diferentes = linhas1 - linhas2
        return list(linhas_diferentes)

    def create_file_list(self, dir_path, filename):
        files = os.listdir(dir_path)
        filesChains = []
        for file in files:
            if file.endswith('.fw'):
                chain = self.get_in_file(dir_path+file, 'NAME')
                filesChains.append(f'{file}={chain}')
        self.write_files(filesChains, filename)

    def check_deleted_files(self, dir_Path):
        oldFileName = dir_Path+'.controller_deleted_files.txt'
        newFileName = dir_Path+'.controller_deleted_files.tmp'
        listDeletedFiles = []
        if os.path.exists(oldFileName):
            self.create_file_list(dir_Path, newFileName)
            listDeletedFiles = self.compare_files(oldFileName, newFileName)
            os.remove(oldFileName)
            os.rename(newFileName, oldFileName)
        else:
            self.create_file_list(dir_Path, oldFileName)
        return listDeletedFiles

    def get_changed_files(self, dir_path):

        # Obtém a data da última verificação a partir do arquivo auxiliar ou usa uma data antiga se não existir
        if os.path.exists(self.last_checked_file):
            with open(self.last_checked_file, 'r') as f:
                last_checked = datetime.datetime.fromisoformat(
                    f.read().strip())
        else:
            last_checked = datetime.datetime.fromisoformat(
                '2000-01-01 00:00:00')

        # Lista os arquivos no diretório
        files = os.listdir(dir_path)

        # Cria uma lista para armazenar os arquivos que foram modificados
        changed_files = []

        # Verifica a data de modificação de cada arquivo e adiciona na lista de arquivos modificados se foi modificado após a última verificação
        for file in files:
            file_path = os.path.join(dir_path, file)
            mod_time = datetime.datetime.fromtimestamp(
                os.path.getmtime(file_path))
            if mod_time > last_checked and os.path.splitext(file)[-1] == '.fw':
                changed_files.append(file)

        # Atualiza a data da última verificação no arquivo auxiliar
        with open(self.last_checked_file, 'w') as f:
            f.write(datetime.datetime.now().isoformat())

        # Retorna a lista de arquivos modificados
        return changed_files

    # services funcitions
    def reload_services_rules(self):

        # recupera todos os arquivos que foram alterados desde de a ultima execussão do script
        modified_files = self.get_changed_files(self.service_dir)
        # remove regras relacioandas a arquivos deletados
        self.remove_Chain_Deleted(self.service_dir)

        if len(modified_files) == 0:
            logging.info(
                'Nenhum arquivo foi modificado desde a ultima verificação')
        else:
            for file in modified_files:
                file = self.service_dir+file
                # TODO Alterar o arquivo para inglês
                nome = self.get_in_file(file, 'NAME')
                ip = self.get_in_file(file, 'IP')
                if (not ip) or (not nome):   # checa  se o arquivo tem o IP e nome da chain para continuar
                    logging.error(
                        f'O arquivo {file} não esta configurado corretamente')
                    # se tiver algum problema,  atualiza a data de modificação do arquivo para que ele seja carregado novamnte
                    self.run_command_no_out(f'touch {file}')
                    continue
                self.create_chain_destination_in_forward(nome, ip)
                erros = self.aply_rules_from_file(file, nome)
                if erros:
                    logging.debug(f'Erros encontrados no serviço:{nome}')
                    self.run_command_no_out(f'touch {file}')
                    for erro in (erros):
                        logging.error(erro)

                else:
                    logging.info(
                        "Regras do Serviço {} recarregadas com  sucesso!".format(nome))

    #  Main menu functions

    def reload_subnet_rules(self):
        pass

    def realod_all_rules(sefl):
        pass

    def list_modified_services(self):
        pass

    def create_new_service(self):
        pass

    def create_new_sub_net(self):
        pass

    def quit():
        quit
