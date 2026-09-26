# Ntheemba Apps

## Repository purpose

This repository is the public evidence and showcase copy of Ntheemba, the
neutral orchestration and conversational runtime for Ntheemba Digital
Services. It was created as an independently viewable implementation slice
for portfolio review while remaining coordinated by the wider platform
repository.

Parent platform: [NTheemba Platform](https://github.com/OddJei/NTheemba-Platform)

Ntheemba interprets requests, applies capability and tenant boundaries, and
routes approved workflows to authoritative systems. It is not the source of
truth for business prices, stock, services, policies or availability.

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
