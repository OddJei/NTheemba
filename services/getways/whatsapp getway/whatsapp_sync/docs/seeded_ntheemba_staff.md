# Seeded ntheemba staff and DB schema

*Database path*: `C:\Users\SMART PC\Documents\NTheemba\services\ntheemba_api\fixtures\dev.sqlite`

## Tables and columns

### affiliate_payouts

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| payout_id | VARCHAR(64) | 1 | None | 0 |
| payment_id | VARCHAR(64) | 1 | None | 0 |
| affiliate_id | VARCHAR(64) | 1 | None | 0 |
| requested_cents | INTEGER | 1 | None | 0 |
| paid_cents | INTEGER | 0 | None | 0 |
| reason | VARCHAR(256) | 0 | None | 0 |
| created_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


### affiliates

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| affiliate_id | VARCHAR(64) | 1 | None | 0 |
| name | VARCHAR(256) | 0 | None | 0 |
| plan | VARCHAR(32) | 0 | None | 0 |
| free_percent | INTEGER | 0 | None | 0 |
| paid_percent | INTEGER | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### analytics_events

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| business_id | VARCHAR(64) | 0 | None | 0 |
| event_type | VARCHAR(64) | 1 | None | 0 |
| user | JSON | 0 | None | 0 |
| properties | JSON | 0 | None | 0 |
| created_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


### businesses

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| business_id | VARCHAR(64) | 1 | None | 0 |
| name | VARCHAR(256) | 0 | None | 0 |
| owner_phone | VARCHAR(32) | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### coupons

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| code | VARCHAR(64) | 1 | None | 0 |
| description | TEXT | 0 | None | 0 |
| discount_percent | INTEGER | 0 | None | 0 |
| active | BOOLEAN | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### idempotency_keys

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| key | VARCHAR(128) | 1 | None | 0 |
| response_code | INTEGER | 0 | None | 0 |
| response_body | JSON | 0 | None | 0 |
| created_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


### inventory_reservations

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| reservation_id | VARCHAR(64) | 1 | None | 0 |
| order_id | VARCHAR(64) | 1 | None | 0 |
| items | JSON | 1 | None | 0 |
| reserved_until | DATETIME | 0 | None | 0 |


### links

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| link_id | VARCHAR(64) | 1 | None | 0 |
| token | VARCHAR(128) | 1 | None | 0 |
| affiliate_id | VARCHAR(64) | 0 | None | 0 |
| product_id | VARCHAR(64) | 0 | None | 0 |
| product_name | VARCHAR(256) | 0 | None | 0 |
| product_sku | VARCHAR(64) | 0 | None | 0 |
| target_phone | VARCHAR(32) | 0 | None | 0 |
| template | TEXT | 0 | None | 0 |
| target | VARCHAR(512) | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |
| active | BOOLEAN | 0 | None | 0 |
| expires_at | DATETIME | 0 | None | 0 |


### media_presigns

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| presign_id | VARCHAR(64) | 1 | None | 0 |
| filename | VARCHAR(256) | 1 | None | 0 |
| content_type | VARCHAR(128) | 0 | None | 0 |
| url | VARCHAR(2048) | 0 | None | 0 |
| expires_at | DATETIME | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### messages

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| message_id | VARCHAR(128) | 1 | None | 0 |
| to | VARCHAR(64) | 1 | None | 0 |
| from | VARCHAR(64) | 1 | None | 0 |
| request_id | VARCHAR(128) | 0 | None | 0 |
| timestamp | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |
| message | TEXT | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### notifications

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| to | VARCHAR(64) | 1 | None | 0 |
| channel | VARCHAR(32) | 1 | None | 0 |
| message | TEXT | 1 | None | 0 |
| meta | JSON | 0 | None | 0 |
| created_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


### objects

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| object_id | VARCHAR(64) | 1 | None | 0 |
| meta | JSON | 0 | None | 0 |


### order_items

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| order_id | VARCHAR(64) | 1 | None | 0 |
| product_id | VARCHAR(64) | 1 | None | 0 |
| qty | INTEGER | 1 | None | 0 |
| unit_price | INTEGER | 1 | None | 0 |
| promoted_by_affiliate_id | VARCHAR(64) | 0 | None | 0 |


### orders

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| order_id | VARCHAR(64) | 1 | None | 0 |
| business_id | VARCHAR(64) | 0 | None | 0 |
| customer_phone | VARCHAR(32) | 1 | None | 0 |
| total_amount | INTEGER | 1 | None | 0 |
| currency | VARCHAR(8) | 0 | None | 0 |
| status | VARCHAR(32) | 0 | None | 0 |
| affiliate_id | VARCHAR(64) | 0 | None | 0 |
| paid_at | DATETIME | 0 | None | 0 |
| confirmation_phrase | VARCHAR(32) | 0 | None | 0 |
| confirmation_expires_at | DATETIME | 0 | None | 0 |
| confirmation_confirmed_at | DATETIME | 0 | None | 0 |
| confirmation_confirmed_by | VARCHAR(32) | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### payments

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| payment_id | VARCHAR(64) | 1 | None | 0 |
| order_id | VARCHAR(64) | 1 | None | 0 |
| amount | INTEGER | 1 | None | 0 |
| method | VARCHAR(32) | 0 | None | 0 |
| status | VARCHAR(32) | 0 | None | 0 |
| paid | BOOLEAN | 1 | None | 0 |
| paid_at | DATETIME | 0 | None | 0 |
| platform_fee_cents | INTEGER | 0 | None | 0 |
| platform_net_cents | INTEGER | 0 | None | 0 |
| msme_payout_cents | INTEGER | 0 | None | 0 |
| affiliates_breakdown | JSON | 0 | None | 0 |
| reconciled | BOOLEAN | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### products

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| product_id | VARCHAR(64) | 1 | None | 0 |
| business_id | VARCHAR(64) | 0 | None | 0 |
| sku | VARCHAR(64) | 0 | None | 0 |
| name | VARCHAR(256) | 1 | None | 0 |
| description | TEXT | 0 | None | 0 |
| price | INTEGER | 1 | None | 0 |
| currency | VARCHAR(8) | 0 | None | 0 |
| images | JSON | 0 | None | 0 |
| attributes | JSON | 0 | None | 0 |


### ratings

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| order_id | VARCHAR(64) | 0 | None | 0 |
| product_id | VARCHAR(64) | 0 | None | 0 |
| business_id | VARCHAR(64) | 0 | None | 0 |
| rating | INTEGER | 1 | None | 0 |
| comment | TEXT | 0 | None | 0 |
| user | JSON | 0 | None | 0 |


### sessions

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| session_id | VARCHAR(64) | 1 | None | 0 |
| user_phone | VARCHAR(32) | 0 | None | 0 |
| object_id | VARCHAR(64) | 1 | None | 0 |
| mode | VARCHAR(32) | 1 | None | 0 |
| created_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |
| expires_at | DATETIME | 0 | None | 0 |


### shipments

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| shipment_id | VARCHAR(64) | 1 | None | 0 |
| order_id | VARCHAR(64) | 1 | None | 0 |
| carrier | VARCHAR(128) | 0 | None | 0 |
| tracking_number | VARCHAR(128) | 0 | None | 0 |
| status | VARCHAR(32) | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### subscriptions

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| subscription_id | VARCHAR(64) | 1 | None | 0 |
| owner_phone | VARCHAR(32) | 1 | None | 0 |
| status | VARCHAR(32) | 1 | None | 0 |
| plan | VARCHAR(64) | 0 | None | 0 |
| started_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |
| meta | JSON | 0 | None | 0 |


### users

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| phone | VARCHAR(32) | 1 | None | 0 |
| name | VARCHAR(128) | 0 | None | 0 |
| is_staff | BOOLEAN | 0 | None | 0 |
| is_registered | BOOLEAN | 0 | None | 0 |
| meta | JSON | 0 | None | 0 |


### webhook_logs

| column | type | notnull | default | pk |
|---|---|---|---|---|
| id | INTEGER | 1 | None | 1 |
| webhook_id | VARCHAR(64) | 1 | None | 0 |
| provider | VARCHAR(64) | 0 | None | 0 |
| payload | JSON | 0 | None | 0 |
| received_at | DATETIME | 0 | CURRENT_TIMESTAMP | 0 |


## Seeded records for test staff

### users
```json
{
  "id": 3,
  "phone": "+260952675580",
  "name": "James Chisulo",
  "is_staff": 0,
  "is_registered": 1,
  "meta": null
}
```

### businesses
```json
{
  "id": 2,
  "business_id": "ntheemba",
  "name": "ntheemba",
  "owner_phone": "+260952675580",
  "meta": null
}
```
### subscriptions
```json
{
  "id": 1,
  "subscription_id": "sub-ntheemba-dev",
  "owner_phone": "+260952675580",
  "status": "active",
  "plan": "trial",
  "started_at": "2025-09-24T10:36:43.865079",
  "meta": null
}
```