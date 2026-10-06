# PRD - Sistema de Gestão de Pousada Vale do Sol

## Problema
Proprietário de pousada precisa de site público + sistema completo de gestão: quartos, calendário unificado, formulário público FNRH, sincronização iCal com Airbnb/Booking/TripLar, templates WhatsApp com PIX, módulo financeiro (receitas/despesas) e gestão de galeria/configurações.

## User Personas
- Anfitrião/Recepção (admin): gerencia tudo pelo painel.
- Hóspede (público): navega pelo site e envia pré-reserva via formulário FNRH (write-only).

## Arquitetura
- Backend FastAPI + MongoDB, JWT auth, RBAC (admin vs público), object storage (Emergent), icalendar, Stripe (sandbox claimable).
- Frontend React + Tailwind + shadcn/ui, react-router.
- Design: paleta terracotta + palm green + areia.
- Agendamentos: `.emergent/crons.yml` (plataforma dispara chamadas HTTP autenticadas por `WEBHOOK_CRON_SECRET`).

## Implementado
### 2026-02 — Base
- Auth JWT, site público, FNRH `/reservar`, painel admin completo (reservas, quartos, calendário, financeiro, iCal, WhatsApp templates, galeria), object storage, iCal auto-sync 15min, voucher PDF, QR code.

### 2026-02 — Motor de Precificação
- 10% sex/sáb, 2º adulto −10%, criança 0-3 (1ª grátis / demais 65%), pets 20.7/27.6/34.5%.
- Classificação automática de 156 raças + fallback manual.

### 2026-02 — Autocomplete + Feriados Nacionais
- Dropdown de raças com teclado.
- Feriados BR fixos + móveis (Páscoa Gregoriana) → sobretaxa 10% automática + badge "🎉 Nome".
- Endpoint `GET /api/public/holidays`.

### 2026-02 — Seção de Pagamento + Link Stripe + Cron (esta sessão)
- **Nav "Pagamento"** no header → âncora `#pagamento` com scroll suave.
- **Badges Visa/Mastercard/Elo** (SVG inline) na seção.
- **Stripe (sandbox claimable)**: `POST /api/reservations/{id}/payment-link` cria Checkout Session dinâmica em BRL. Webhook `POST /api/stripe/webhook` marca reserva como `paid` + `status=confirmed` idempotentemente. Admin tem botões "Gerar link" / "Copiar" / "Enviar por WhatsApp" por reserva. Coluna "Pagamento" mostra badge Pago/Aguardando.
- **Lembrete 3 dias**: cron diário 12:00 America/Sao_Paulo em `.emergent/crons.yml` → `POST /api/cron/checkin-reminder` (auth Bearer `WEBHOOK_CRON_SECRET`) → envia mensagem com PIX + link Stripe para reservas confirmadas/pendentes. Endpoint admin `/api/admin/cron/checkin-reminder/run` para trigger manual.
- **Visibilidade admin**: nova coluna "Reservado em" + "Origem" (Direto/Site/OTA) na lista; tooltip e popup do Calendário mostram guest + origem + data de criação + status.
- Testes: 11/11 backend + frontend ok (iteration_8.json). Tax mode selecionado: **DIY** (Stripe processa pagamento, sem auxílio fiscal; apropriado para hospedagem no Brasil onde o valor já inclui impostos).

## Backlog / P1
- Widget de reserva na Home com seletor de datas + hóspedes.
- Auto-fill de endereço por CEP no FNRH.
- Manter override manual de porte de pet ao editar raça.
- Acessibilidade: `DialogDescription` em modais do admin.

## Backlog / P2
- Pacotes/upsells pagos.
- Link de auto-cancelamento por e-mail.
- Refatorar `server.py` (>2000 linhas) em routers.

## Backlog / P3
- Multi-idioma (EN/ES).
- Área do hóspede logado com histórico.

## Stripe — modo de impostos
- **Atual: DIY** — Stripe só processa o pagamento.
- Pode trocar quando quiser via chat (opções restantes: "Stripe calcula o imposto" +0,5% por transação).
- Chaves ativas são da sandbox claimable; para ir ao vivo, abrir **Manage → Payments** e completar o KYC (as chaves live substituem automaticamente no deploy).

## Credenciais de Teste
Ver `/app/memory/test_credentials.md`.
