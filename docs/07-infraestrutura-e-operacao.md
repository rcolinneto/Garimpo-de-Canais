# 07 — Infraestrutura e Operação

## Deploy

- Tudo empacotado via Docker Compose com três serviços: `app` (API + jobs), `dashboard` (Streamlit), `db` (PostgreSQL). Um único `docker-compose.yml` sobe o ambiente completo em qualquer VPS (ex.: um droplet DigitalOcean, uma VM pequena de qualquer provedor, ou até uma máquina da própria empresa).
- Não há necessidade de infraestrutura elaborada (Kubernetes, múltiplas regiões, etc.) para o volume esperado — isso seria over-engineering para um sistema de uso interno de uma pessoa/pequeno time.
- `.env` com as credenciais (chave da API do YouTube, credenciais do banco, credenciais de SMTP para alertas) — nunca commitado no repositório; `.env.example` documenta quais variáveis existem.

## Agendamento

- APScheduler rodando dentro do próprio processo da aplicação, com os jobs de descoberta (ex.: 1x/dia) e snapshot (ex.: 1x/dia) configurados por cron expression em `config/settings.py`.
- Alternativa igualmente válida: cron do próprio sistema operacional chamando scripts Python (`python -m src.scheduler.jobs snapshot`). Mais simples ainda de depurar, ao custo de não ter uma UI de monitoramento dos jobs — para o volume deste projeto, tanto faz; a Claude Code pode implementar a que for mais simples de manter.
- Se no futuro o número de canais/nichos monitorados crescer muito, migrar para Celery + Redis, que dá retry automático, execução distribuída e melhor observabilidade.

## Logs e monitoramento

- Log estruturado (nível INFO para execução normal, ERROR para falhas) gravado em arquivo e também refletido na tabela `collection_runs` (ver `03-modelo-de-dados.md`), que é a fonte de verdade sobre "a coleta rodou hoje?" — o dashboard pode inclusive ter um indicador de saúde baseado nessa tabela ("última coleta bem-sucedida: há 6 horas").
- Alertar (e-mail simples) se um job falhar, para não descobrir só quando o dashboard estiver com dados desatualizados há dias.

## Segurança

- Chave da API do YouTube e demais segredos apenas em variáveis de ambiente/secret manager do provedor de hospedagem, nunca em código.
- Dashboard atrás de senha (ver `06-dashboard.md`), especialmente porque ele expõe dados agregados de análise de mercado que podem ser sensíveis competitivamente para a empresa.
- Backups automáticos do PostgreSQL (mesmo que só um dump diário para armazenamento externo) — o histórico de snapshots é o ativo mais valioso do sistema e não é recriável se perdido (dados passados de canais não podem ser "recoletados" retroativamente).

## Backup e restore

Ter backup sem nunca ter testado o restore é o mesmo que não ter backup — só se descobre que algo está errado (dump corrompido, credencial errada, versão incompatível do Postgres) na hora em que já se perdeu o dado. Por isso, o processo abaixo cobre os dois lados.

### Backup

- Job diário (pode ser o mesmo agendador do resto do sistema, ou um cron simples do sistema operacional) rodando `pg_dump` contra o banco e enviando o arquivo para um armazenamento fora da VPS (ex.: um bucket de object storage, ou até um repositório privado dedicado a backups) — nunca só no disco da mesma máquina, senão a perda do servidor leva o banco e o backup junto.
- Reter pelo menos os últimos 7 dumps diários (rotação simples), para ter margem de recuperar mesmo se um problema for percebido alguns dias depois de acontecer.
- Nomear os arquivos com data (`garimpo_YYYYMMDD.dump`) para facilitar localizar o ponto de restauração certo.

### Restore (passo a passo)

1. Provisionar (ou reaproveitar) uma instância limpa do PostgreSQL na mesma versão maior usada em produção.
2. Copiar o arquivo de dump desejado para a máquina/container que vai rodar o restore.
3. Restaurar com `pg_restore` (ou `psql` se o dump for em formato texto) apontando para o banco vazio: `pg_restore --clean --if-exists -d <DATABASE_URL_do_banco_alvo> <arquivo.dump>`.
4. Rodar `alembic upgrade head` em seguida, **somente se** houver migrations mais novas que a versão do schema no dump restaurado (o dump já inclui o schema no estado em que estava; isso só é necessário se o restore for de um backup antigo e o código já tiver avançado o schema depois).
5. Validar: contar linhas de `channels` e `channel_snapshots` e comparar com uma expectativa aproximada (não deve vir zerado nem muito abaixo do esperado); conferir `collection_runs` para ver se a última execução registrada bate com a data do dump restaurado.
6. Apontar a aplicação (`DATABASE_URL`) para o banco restaurado e subir normalmente.

### RPO/RTO alvo (realista para este projeto)

- **RPO (quanto dado se pode perder)**: até 24 horas — aceitável dado que o backup é diário e a fonte primária (YouTube) permite recuperar o estado *atual* de qualquer canal a qualquer momento; o que se perde de fato num intervalo de 24h é histórico de snapshot, não o canal em si.
- **RTO (quanto tempo até voltar a operar)**: algumas horas — não há exigência de recuperação imediata, já que o sistema é uma ferramenta de análise interna, não algo com usuários externos dependendo de disponibilidade em tempo real.

### Teste do processo de restore

Rodar esse procedimento de teste **antes** de precisar dele de verdade — por exemplo, uma vez a cada trimestre, restaurando o dump mais recente em um ambiente descartável e conferindo os passos 5 acima. Isso é o que garante que o backup vale alguma coisa quando for realmente necessário.

## Estimativa de custo operacional

| Item | Custo estimado |
|---|---|
| YouTube Data API v3 | Gratuito (dentro da cota de 10.000 unidades/dia) |
| VPS pequena (2 vCPU / 4GB RAM) | Baixo custo mensal, variável por provedor — cotar na hora da implementação |
| PostgreSQL | Incluso na mesma VPS via Docker, ou um serviço gerenciado básico |
| E-mail para alertas | Gratuito até volumes baixos (ex.: via SMTP de provedores com tier gratuito) |

## Manutenção esperada ao longo do tempo

- A YouTube Data API v3 é estável, mas ainda vale reservar tempo periódico para checar se o coletor continua funcionando conforme o volume de canais monitorados cresce (ex.: necessidade de rotacionar chaves de API).
- Regras de detecção de monetização (`05-motor-monetizacao-e-score.md`) devem ser revisadas periodicamente conforme novos padrões de link/plataforma de monetização surgirem no mercado.
