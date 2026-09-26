# Ntheemba Apps

Ntheemba is split into three working areas.

## Bot

Path: `bot/`

The orchestration app for intent handling, workflow state, trusted-data calls, customer/session isolation, confirmation flows, and handover.

## WhatsApp Gateway

Path: `whatsapp-gateway/`

The transport/runtime app for WhatsApp delivery, queueing, retries, session runtime, signatures, and delivery infrastructure.

## Apps Script Bridge

Path: `appscript-bridge/`

The bridge documentation and Apps Script integration material used to connect Ntheemba to trusted Google Apps Script interfaces.

## Boundary

Ntheemba must not be the source of truth for business facts. Prices, stock, services, policies, and availability come from approved TradeFlow or Catalogue interfaces.
