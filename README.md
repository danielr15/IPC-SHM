# Simulador de IPC via Memória Compartilhada Protegida

Trabalho Final — Sistemas Operacionais (IFCE)  
Tema: simulação visual de IPC por memória compartilhada com mecanismos de proteção configuráveis.

## Tópicos integrados

- **Gerenciamento de Memória:** segmento SHM, células/endereços, leitura/escrita, corrupção de dados
- **Processos + Sincronização:** mutex, semáforo, RW-lock, filas de espera
- **Impasses (opcional):** cenário `deadlock_demo` com mutex por célula

## Arquitetura

```
Navegador (React)  ←→  API REST + WebSocket (FastAPI)  ←→  Simulação (Python)
```

## Pré-requisitos

- Python 3.11+
- Node.js 20+
- (Opcional) Docker e Docker Compose

## Execução local

Na raiz do projeto:

```powershell
npm run backend    # terminal 1
npm run frontend   # terminal 2
```

Ou só o backend:

```powershell
cd backend
python run.py
```

No PowerShell também funciona: `.\run.ps1`

Se a porta **8000** estiver ocupada, o `run.py` usa automaticamente a próxima livre (ex.: 8001) e avisa no terminal. Nesse caso, crie `frontend/.env`:

```
VITE_API_PORT=8001
```

Para liberar a 8000 manualmente:

```powershell
netstat -ano | findstr :8000
Stop-Process -Id <PID> -Force
```

### Backend (manual)

```powershell
cd backend
pip install -r requirements.txt
python run.py
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Abra [http://localhost:5173](http://localhost:5173). O Vite faz proxy de `/api` e `/ws` para o backend.

### Docker Compose

```powershell
docker compose up --build
```

- Frontend: http://localhost:5173  
- API: http://localhost:8000  
- Docs da API: http://localhost:8000/docs  

## API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/api/state` | Estado completo (memória, processos, métricas) |
| GET | `/api/scenarios` | Lista cenários disponíveis |
| POST | `/api/protection` | `{ "mode": "none\|mutex\|semaphore\|rwlock\|rwlock_global\|cell_mutex", "k": 3 }` |
| POST | `/api/scenario` | `{ "name": "race_write" }` |
| POST | `/api/start` | Inicia simulação automática |
| POST | `/api/stop` | Pausa |
| POST | `/api/step` | Avança 1 tick |
| POST | `/api/reset` | Reinicia cenário atual |
| WS | `/ws/events` | Stream de estado em tempo real |

### Exemplo — mudar proteção via curl

```powershell
curl -X POST http://localhost:8000/api/protection `
  -H "Content-Type: application/json" `
  -d '{"mode": "mutex"}'
```

## Modos de proteção

| Modo | Descrição |
|------|-----------|
| `none` | Sem proteção — race conditions causam corrupção e crash |
| `mutex` | Exclusão mútua global no segmento SHM |
| `semaphore` | Até K processos simultâneos na região |
| `rwlock` | Múltiplos leitores ou um escritor **por célula** |
| `rwlock_global` | RW-lock global — checkbox **preferência por leitores** ou **justo** |
| `cell_mutex` | Mutex independente por célula (deadlock) |

## Cenários de teste

Os cenários definem um **perfil de contenção** (proteção, nº de processos, probabilidade R/W). Cada processo:

- inicia após um **atraso aleatório**;
- espera um tempo aleatório (**think time**) entre operações;
- escolhe **qualquer célula** do segmento, com operação e duração aleatórias;
- **permanece crashed** após corrupção (sem reinício).

**Modo livre** (nenhum cenário selecionado): escolha proteção e número de processos (1–16) e execute

O cenário **Impasse garantido** permanece **scriptado** — o impasse exige ordem fixa de locks.

| Cenário (id) | Proteção | Comportamento |
|---------|----------|---------------|
| Corrida de escrita | `none` | Escritores em endereços aleatórios |
| Leitura e escrita mistas | `none` | Leitores e escritores concorrentes |
| Escrita com exclusão mútua | `mutex` | Fila dinâmica, sem corrupção |
| Leituras simultâneas | `rwlock` | Leitores em paralelo (por célula) |
| Escritor e leitores | `rwlock` | Escritor bloqueia leitores na mesma célula |
| Leituras globais em paralelo | `rwlock_global` | Leitores em células diferentes ao mesmo tempo |
| Escritor bloqueia toda a memória | `rwlock_global` | Escritor trava o segmento inteiro |
| Vagas limitadas | `semaphore` K=2 | Acesso limitado por semáforo |
| Impasse aleatório | `cell_mutex` | Impasse pode surgir ao acaso |
| Impasse garantido | `cell_mutex` | Roteiro fixo |

### Rodar testes automatizados do motor

```powershell
cd backend
python -m tests.run_scenarios
```

## Métricas exibidas

- Taxa de corrupção (%)
- Throughput (ops/tick)
- Tempo médio de espera
- Bloqueios, crashes, deadlocks
- Paralelismo máximo de leitores (RW-lock)

## Estrutura do projeto

```
finalSO/
├── backend/          # FastAPI + motor de simulação
├── frontend/         # React + TypeScript + Vite
├── docs/             # Relatorio
└── docker-compose.yml
```

## Referência

Tanenbaum & Bos — *Sistemas Operacionais Modernos* (memória compartilhada, semáforos, mutex, impasses).
