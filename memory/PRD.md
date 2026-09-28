# PRD - Sistema de Gestão de Pousada Vale do Sol

## Problema
Proprietário de pousada precisa de site público + sistema completo de gestão: quartos, calendário unificado, formulário público FNRH, sincronização iCal com Airbnb/Booking/TripLar, templates WhatsApp com PIX, módulo financeiro (receitas/despesas) e gestão de galeria/configurações.

## User Personas
- Anfitrião/Recepção (admin): gerencia tudo pelo painel.
- Hóspede (público): navega pelo site e envia pré-reserva via formulário FNRH (write-only).

## Arquitetura
- Backend FastAPI + MongoDB, JWT auth, RBAC (admin vs público write-only), object storage (Emergent), icalendar parser/generator.
- Frontend React + Tailwind + shadcn/ui, react-router.
- Design: paleta terracotta + palm green + areia (evita gradientes roxo/azul genéricos).

## Implementado
### 2026-02-28
- Auth JWT (`/api/auth/login`, `/me`, `/change-password`) com seed admin `admin@pousada.com / pousada2024`.
- Site público `/`: hero, sobre, acomodações, galeria com lightbox, contato, PIX copiar, floating WhatsApp.
- Formulário público FNRH `/reservar` (write-only, aceite obrigatório).
- Painel admin `/admin`: Dashboard, Calendário, Reservas (CRUD + WhatsApp PIX), Quartos, Site & Galeria, iCal export/import, WhatsApp Templates, Financeiro, Conta.
- Object storage integrado para upload de fotos.
- iCal export/import bi-direcional + auto-sync 15min.

### Feb/2026 - Motor de Precificação + Pets
- `compute_pricing` custom: sobretaxa 10% sexta/sábado, 2º adulto -10%, 1ª criança 0-3 grátis, demais 65%, pets pequeno 20.7% / médio 27.6% / grande 34.5% da diária.
- Classificação automática de raça de pet via `breeds.py` (156 raças) + fallback manual com aviso.
- Voucher PDF via `reportlab`, QR code do link de reserva, envio WhatsApp webhook.
- Financeiro com exportação CSV e PDF mensal.

### Feb/2026 - Autocomplete + Feriados Nacionais (esta sessão)
- **Autocomplete de raças** no formulário público: dropdown filtrando as 156 raças conforme o usuário digita, navegação por teclado (↑ ↓ Enter Esc), clique externo fecha.
- **Feriados nacionais brasileiros** automáticos no motor de precificação: módulo `holidays.py` com feriados fixos + móveis (Carnaval, Sexta-feira Santa, Corpus Christi calculados via algoritmo de Páscoa Gregoriano), cobrindo qualquer ano.
- Feriados aplicam a mesma sobretaxa de fim de semana (10%). Cada noite retorna `is_national_holiday` + `holiday_name`.
- Novo endpoint público `GET /api/public/holidays?year=YYYY` (retorna ano atual + próximo).
- Estimativa detalhada exibe "🎉 Tiradentes" (ou nome do feriado) na noite correspondente.
- Testado: 7/7 backend, 10/10 frontend (iteration_7.json).

## Backlog / P1
- Widget de reserva na Home (`PublicSite.js`) com seletor de datas + hóspedes que filtra quartos disponíveis.
- Auto-fill de endereço por CEP no formulário FNRH.
- Correção UX: manter override manual de porte de pet ao editar raça (perde `_manual: true` a cada tecla).
- Acessibilidade: adicionar `DialogDescription` visualmente oculto nos modais de `RoomsPage.js` / `ReservationsPage.js`.

## Backlog / P2
- Pacotes/upsells (café premium, passeio de barco) como add-ons pagos.
- Link de auto-cancelamento por e-mail dentro do prazo.
- Refatorar `server.py` (>1900 linhas) em serviços: `pricing_service`, `pdf_service`, `ical_service`.

## Backlog / P3
- Multi-idioma (EN/ES) no site público.
- Área do hóspede logado com histórico + repetir reserva.

## Credenciais de Teste
Ver `/app/memory/test_credentials.md`.
