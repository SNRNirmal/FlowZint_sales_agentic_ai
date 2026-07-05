"""Simulated CRM webhook payload generator, used by demo/seed_deals.json
and the /webhooks/crm route. Swap for a real Salesforce/HubSpot webhook
post-hackathon."""

SAMPLE_PAYLOAD = {
    "customer_name": "Northwind Logistics",
    "value": 180000,
    "discount_percent": 18,
    "product_type": "custom",
    "customer_segment": "enterprise",
    "stage": "verbal_agreement",
}
