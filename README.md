# War LAN

Jogo de estratégia por turnos para 2–6 pessoas na mesma LAN. Implementação em
**Python 3.10+ / Pygame**, com mapa vetorial offline, host autoritativo TCP e
descoberta UDP por broadcast. Não há serviço em nuvem nem cadastro.

Python reduz diferenças de sockets/empacotamento entre Linux e Windows. Pygame
usa SDL para renderização e eventos; um jogo por turnos com 195 territórios não
precisa de C++ para simulação. O cliente renderiza a 60 FPS como alvo, não como
garantia; os dados geográficos são simplificados para limitar o custo por frame.
O host decide regras, dados, propriedade e vitória. Missões dos demais jogadores
não aparecem nos snapshots enviados ao cliente.

O mapa inclui 193 membros da ONU e os Estados observadores Vaticano/Santa Sé e
Palestina. Leia [DATA_SOURCES.md](DATA_SOURCES.md): a base não certifica fronteiras
de 2026 e as rotas marítimas são conexões de jogo, não limites oficiais.

## Estrutura

```text
assets/README.md               localização e uso dos assets
src/war_lan/
  assets/world.json           polígonos, países, regiões, adjacências
  assets/ODbL-1.0.txt          licença do banco geográfico
  model.py                    regras independentes de GUI/rede
  network.py                  anúncios UDP, host TCP, cliente TCP
  ui.py                       menu, lobby, mapa, zoom/pan, ações
  __main__.py                 entrada python -m war_lan
run_game.py                   entrada para execução e PyInstaller
tools/build_map.py            reprodução/auditoria do mapa (opcional)
tests/                        regras, TCP, UDP e interface headless
packaging/PKGBUILD            pacote pacman a partir do checkout local
pyproject.toml                wheel, dados e comando war-lan
requirements.txt              dependência de runtime fixada
```

## Arch Linux

Execute na raiz do checkout, normalmente `/workspace/test` no ambiente Codex.
Opção com o Pygame fornecido pelo Arch:

```sh
sudo pacman -S --needed python python-pygame
python run_game.py
```

Alternativa com a versão fixada de Pygame CE em ambiente virtual (não instale
Pygame e Pygame CE juntos no mesmo ambiente):

```sh
sudo pacman -S --needed python python-pip
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_game.py
```

Para pacote instalável pelo pacman, a receita local compila o checkout adjacente:

```sh
sudo pacman -S --needed base-devel python-build python-installer \
  python-setuptools python-wheel python-pygame
cd packaging
makepkg -si
war-lan
```

A receita não está publicada no AUR. Para publicar uma release lá, substitua a
origem local por um arquivo de release versionado em `source`, com SHA-256,
e gere `.SRCINFO` com `makepkg --printsrcinfo`. O build não deve baixar
bibliotecas via pip: as dependências são resolvidas pelo pacman.

## Windows 10/11

Instale Python 3.12 de https://www.python.org/downloads/windows/ e abra
PowerShell na raiz do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_game.py
```

Executável standalone, **gerado no Windows**, sem exigir Python na máquina de
destino:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name WarLAN --paths src --add-data "src/war_lan/assets:war_lan/assets" run_game.py
.\dist\WarLAN.exe
```

Não há cross-compilação de `.exe` a partir do Linux nesse fluxo. O pacote Arch e
a execução Windows exigem validação nos respectivos sistemas; os testes desta
implementação foram executados em Linux no ambiente de desenvolvimento.

## Jogar

1. Digite o nome, clique em **Criar partida LAN** no computador anfitrião.
2. Outros jogadores abrem o jogo e clicam na partida em **Jogos LAN disponíveis**.
   Ela é anunciada a cada segundo e desaparece quatro segundos após o último
   anúncio. O anfitrião também joga como cliente local.
3. Se a descoberta estiver bloqueada, use o IPv4 do anfitrião e porta TCP,
   por exemplo `192.168.1.20:47777`. `ip -4 addr` no Linux ou `ipconfig` no Windows
   mostram endereços locais; escolha a interface da LAN, não loopback.
4. O criador escolhe dominação ou missões e inicia após ao menos dois jogadores.

Portas padrão: **47777/TCP** para a partida e **47778/UDP** para descoberta.
Personalização, igual em todas as máquinas:

```sh
python run_game.py --port 48000 --discovery-port 48001
```

Configure o firewall apenas para a rede local confiável. No Windows, autorize
o Python/executável no perfil **Privado**; não abra o jogo à Internet. Broadcast
IPv4 não atravessa roteadores/VLANs e pode ser impedido por isolamento de clientes
Wi-Fi ou VPN. A conexão direta resolve apenas bloqueio do broadcast: TCP ainda
precisa alcançar o anfitrião. Nenhuma regra de firewall é alterada automaticamente.

## Controles e regras

- Roda do mouse: zoom centrado no cursor. Botão direito e arraste: pan.
- Clique: origem. **Shift + clique**: destino. Marcadores permitem selecionar
  Estados pequenos. Zoom mostra nome e tropas; passar o mouse também mostra
  país, dono e tropas. Cores dos seis jogadores identificam o dono.
- **Editar quantidade**: digite o número; **Aplicar ação** ou Enter confirma.
  Esc encerra a edição de texto.
- A seleção desenha as adjacências permitidas, incluindo rotas marítimas.

Distribuição inicial aleatória equilibrada, três tropas por país. Sem cartas,
objetivos de eliminação ou fase de colocação inicial manual nesta versão.

1. **Reforço**: `max(3, países // 3)` mais `max(2, tamanho_da_região // 5)` para
   cada região inteira dominada. Todos os reforços devem ser distribuídos antes
   de atacar. Cada ação pode distribuir qualquer parte da reserva.
2. **Ataque**: origem própria com pelo menos duas tropas e destino inimigo
   adjacente. Uma ação rola até três dados de ataque e dois de defesa; pares
   ordenados decrescentemente removem uma tropa do perdedor, empate para defesa.
   Após conquista, até o número de dados de ataque é transferido automaticamente,
   sempre deixando uma tropa na origem. O jogador repete ataques ou avança fase.
3. **Movimentação**: uma transferência opcional entre dois países próprios
   ligados por um caminho inteiramente próprio, incluindo rotas marítimas.
   Deve restar uma tropa na origem. Transferir encerra o turno; avançar pula essa
   transferência. Jogadores sem países são pulados.

Dominação exige **156 dos 195 países (80%)**. Missões exigem dominar duas regiões
sorteadas e pelo menos 60 países. As missões são privadas por cliente; o host tem
acesso a todo estado. O sorteio não promete equilíbrio entre regiões de tamanhos
diferentes. Vitória é verificada após cada ação válida e impede novas ações.

O protocolo usa mensagens JSON delimitadas por newline, com versão e limite
64 KiB. Comandos não podem substituir o tabuleiro nem escolher resultados de
dados. O host valida turno, propriedade, fase, quantidade e caminhos, serializando
mutações sob lock. A GUI recebe eventos por fila, sem manipular Pygame em threads.

Limitações: partidas ficam apenas em memória, sem bots, reconexão, transferência
de host ou persistência. Desconexão pausa a partida; use **Sair**, reabra o lobby e
inicie novamente. Sem criptografia, senha ou autenticação forte; destina-se à LAN
confiável. O hostname/IP anunciado não é prova de identidade. Não há bandeiras
nacionais; a implementação usa a alternativa de cores dos proprietários.

## Validação

Com a instalação de runtime concluída:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

PowerShell:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes cobrem regras de turnos/combate, conectividade dos 195 países, validação
de comandos, vitória/missões, fluxo real TCP entre host e dois clientes,
descoberta UDP inclusive broadcast, enquadramento de mensagens e renderização
headless de menu/lobby/mapa. O teste de broadcast exige uma máquina que permita
broadcast local; uma falha indica condição de rede a investigar, não deve ser
silenciada. Testar em duas máquinas físicas continua necessário para validar
firewalls e descoberta através do Wi-Fi/Ethernet de destino.

Para gerar wheel Linux/Windows:

```sh
.venv/bin/python -m pip install build
.venv/bin/python -m build
```

A wheel inclui o mapa e a licença dos dados. Para atualizar/reproduzir o mapa,
consulte `DATA_SOURCES.md`; não há download de dados ao abrir o jogo.
