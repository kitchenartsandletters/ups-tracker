<!-- ShipStation V2 Tracking Documentation -->

## Prerequisites

- **Enable Shipping API Add-On**: Ensure the Shipping API add-on is enabled in your ShipStation account under _Settings > Add‑Ons_. citeturn6search1
- **Generate API Key**: Obtain your API key in _Settings > Account > API Settings_. citeturn6search1

## Authentication

All requests require the `Authorization` header with your API key as a Bearer token:
```http
Authorization: Bearer YOUR_API_KEY
``` citeturn3search9

## Shipments Endpoints

Shipments are at the core of retrieving tracking numbers. The V2 API exposes these endpoints: citeturn6search0
- `GET /v2/shipments`
- `GET /v2/shipments/{shipment_id}`
- `GET /v2/shipments/external_shipment_id/{external_shipment_id}`
- `PUT /v2/shipments/{shipment_id}/cancel`
- `GET /v2/shipments/{shipment_id}/rates`
- `POST /v2/shipments/{shipment_id}/tags/{tag_name}`
- `DELETE /v2/shipments/{shipment_id}/tags/{tag_name}`

### Shipment Object Structure

The returned Shipment object includes the master tracking number:
```json
{
  "shipmentId": "se-123456",
  "carrierCode": "stamps_com",
  "serviceCode": "usps_priority",
  "trackingNumber": "9400111899561704681189",
  ...
}
``` citeturn1view0

## Retrieving Tracking Numbers

### List Shipments

```bash
curl -X GET "https://ssapi.shipstation.com/v2/shipments?carrierCode=usps" \
     -H "Authorization: Bearer YOUR_API_KEY"
```
Each item’s `trackingNumber` field contains the carrier’s master tracking number. citeturn1view0

### Get Single Shipment

```bash
curl -X GET "https://ssapi.shipstation.com/v2/shipments/se-123456" \
     -H "Authorization: Bearer YOUR_API_KEY"
```
Parse the `trackingNumber` from the response. citeturn3search2

### Get by External ID

```bash
curl -X GET "https://ssapi.shipstation.com/v2/shipments/external_shipment_id/ABC123" \
     -H "Authorization: Bearer YOUR_API_KEY"
```
Returns the Shipment object including `trackingNumber`. citeturn3search2

### Package-Level Tracking

For multi-package shipments:
```bash
curl -X GET "https://ssapi.shipstation.com/v2/shipments/se-123456/rates" \
     -H "Authorization: Bearer YOUR_API_KEY"
```
Inspect `packages[].tracking_number` for each package. citeturn5search3

## Labels Endpoint

The Labels endpoint provides per-label tracking numbers:
- `GET /v2/labels`
Each label object includes:
```json
{
  "labelId": "se-987654",
  "tracking_number": "782758401696",
  ...
}
``` citeturn4search6

## Notes

- Some carriers only allow one package per shipment. Multi-package shipments may error out if unsupported. citeturn6search7
