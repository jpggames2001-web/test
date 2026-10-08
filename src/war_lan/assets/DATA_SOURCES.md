# Dados geográficos e escopo

O jogo inclui **195 territórios jogáveis**: os 193 Estados membros das Nações
Unidas, mais os Estados observadores Santa Sé (representada pelo Vaticano) e
Palestina. A ONU não é uma autoridade universal de reconhecimento de Estados;
essa lista é um critério de seleção, não uma declaração sobre disputas.

A lista deriva do campo `unMember` de
[mledoze/countries](https://github.com/mledoze/countries), acrescida de `VAT` e
`PSE`. Nomes em português, códigos ISO e coordenadas vêm dessa base. Licença:
**ODbL 1.0**, incluída em `src/war_lan/assets/ODbL-1.0.txt`. O banco derivado
`world.json` é disponibilizado sob ODbL 1.0; o código do jogo usa MIT.

As formas vêm de **Natural Earth, Admin 0 Countries, escala 1:10 milhões**:
https://www.naturalearthdata.com/about/terms-of-use/ (domínio público).
Fonte: https://github.com/nvkelso/natural-earth-vector . Simplificação topológica
com tolerância 0,025 graus reduz o custo de renderização; projeção equiretangular.
Estados sem polígono disponível continuam selecionáveis por marcador. Áreas de
entidades que não são parte dos 195 registros selecionados não são jogáveis.
Dependências não são territórios de conquista separados.

**Não há certificação de fronteiras oficiais de 2026.** Natural Earth contém
escolhas cartográficas para áreas disputadas; simplificação e seleção de registros
não corrigem essas escolhas. Fronteiras de fato, reivindicações e reconhecimento
não são conceitos equivalentes. O mapa não é adequado para referência jurídica.

Adjacências têm origem rastreável em `edges`:

- `land-simplified`: contato/distância inferior a 0,00001 grau nos polígonos
  originais, antes da simplificação. É uma extração geométrica, não uma auditoria
  diplomática de todas as fronteiras terrestres.
- `land-or-causeway`: conexões explícitas de microestados e pontes/causeways.
- `sea-gameplay`: rotas de jogo explícitas ou ligações por proximidade para
  ilhas/componentes desconectados. **Não são fronteiras marítimas oficiais nem
  rotas estratégicas validadas por especialista.** Ao selecionar uma origem,
  a interface desenha todas as conexões válidas para o combate.

As sete regiões são grupos de jogo: América do Norte (Canadá/EUA), América Latina
e Caribe (inclui México), Europa, Oriente Médio e Norte da África, África
Subsaariana, Ásia Central e Ásia-Pacífico. Não se afirma que esses grupos sejam
uma classificação da ONU; Europa não implica participação na União Europeia.

## Reprodução do banco

O banco offline já está incluído; Shapely **não** é dependência de runtime.
Para reproduzir, obtenha os arquivos das fontes acima, instale `shapely==2.2.0`
em um ambiente separado e execute:

```sh
python tools/build_map.py --geometry /caminho/ne_10m_admin_0_countries.geojson \
  --countries /caminho/countries.json
```

Snapshots consultados durante esta implementação (o gerador verifica SHA-256):

Natural Earth commit `ca96624a56bd078437bca8184e78163e5039ad19`; countries
commit `c2ac0049c14edcf2436c7aa1b2493222a020b462`. URLs fixadas:

- https://raw.githubusercontent.com/nvkelso/natural-earth-vector/ca96624a56bd078437bca8184e78163e5039ad19/geojson/ne_10m_admin_0_countries.geojson
- https://raw.githubusercontent.com/mledoze/countries/c2ac0049c14edcf2436c7aa1b2493222a020b462/countries.json

```text
ne_10m_admin_0_countries.geojson
239eec57ac17f100a11e2536cffc56752c318b50ae765b0918ff7aab4ce8f255
countries.json
913e5d716f9dc6b59881ee23488d47f5fda52070d1a34cac5fa327c9e61d8f7c
```

URLs consultadas: `raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson`
e `raw.githubusercontent.com/mledoze/countries/master/countries.json`.
Essas URLs são móveis: se o conteúdo mudar, localize o snapshot correspondente;
não desligue a verificação. Audite novos dados e atualize a proveniência em uma
alteração separada ao atualizar o mapa.
