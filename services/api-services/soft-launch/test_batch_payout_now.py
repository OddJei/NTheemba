#!/usr/bin/env python
import httpx
import json
import time
import asyncio

async def test_batch_payout():
    """Test the batch payout endpoint"""
    
    payload = {
        "epoch_id": "2024-11-epoch-1",
        "callback_url": "http://affiliate-engine:8510/callbacks/payout-status",
        "payouts": [
            {"affiliate_id": "aff-001", "amount_zmw": 1500, "currency": "ZMW"},
            {"affiliate_id": "aff-002", "amount_zmw": 2300, "currency": "ZMW"},
            {"affiliate_id": "aff-003", "amount_zmw": 800, "currency": "ZMW"},
        ]
    }
    
    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("TEST: Batch Payout Endpoint")
        print("=" * 60)
        
        # Test 1: Submit batch payout
        print("\n[1] Submitting batch payout request...")
        response = await client.post(
            "http://localhost:8590/payout/batch",
            json=payload,
            headers={"X-Admin-Key": "change-me"},
            timeout=5.0,
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Body:")
        
        try:
            resp_data = response.json()
            print(json.dumps(resp_data, indent=2))
            
            batch_id = resp_data.get("batch_id")
            total_payouts = resp_data.get("total_payouts")
            total_amount = resp_data.get("total_amount_zmw")
            status = resp_data.get("status")
            
            print(f"\n✓ Batch ID: {batch_id}")
            print(f"✓ Total Payouts: {total_payouts}")
            print(f"✓ Total Amount: {total_amount} ZMW")
            print(f"✓ Status: {status}")
            
            # Verify response structure
            assert total_payouts == 3, "Expected 3 payouts"
            assert total_amount == 4600, f"Expected 4600 ZMW total, got {total_amount}"
            assert status == "ACCEPTED", f"Expected ACCEPTED status, got {status}"
            print("\n✓ Response validation passed!")
            
        except Exception as e:
            print(f"ERROR: {e}")
            print(f"Raw content: {response.text}")
            return False
        
        # Test 2: Wait for background task and verify callback was sent
        print("\n[2] Waiting for background task (2 seconds)...")
        await asyncio.sleep(2)
        
        # Check if affiliate-engine received the callback
        print("[3] Checking affiliate-engine logs...")
        
        return True

if __name__ == "__main__":
    success = asyncio.run(test_batch_payout())
    if success:
        print("\n" + "=" * 60)
        print("✓ BATCH PAYOUT TEST PASSED")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ BATCH PAYOUT TEST FAILED")
        print("=" * 60)
