#!/usr/bin/env node

/**
 * Script to restart WhatsApp sessions for all synced businesses
 * Run this when the app comes back up after downtime
 *
 * Usage:
 *   npm run restart-sessions
 *   or
 *   node restart_sessions.js
 *
 * Environment Variables:
 *   API_BASE_URL - Base URL for the API service (default: http://localhost:8000)
 *   WHATSAPP_SYNC_URL - Base URL for the WhatsApp sync service (default: http://localhost:3000)
 *
 * The script will:
 * 1. Query all businesses with sync_status = 'active'
 * 2. For each business, start a WhatsApp session using their owner_phone
 * 3. Report success/failure for each business
 */

const axios = require('axios');
require('dotenv').config();

// Configuration
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const WHATSAPP_SYNC_URL = process.env.WHATSAPP_SYNC_URL || 'http://localhost:3000';

async function getSyncedBusinesses() {
  try {
    console.log('🔍 Fetching synced businesses from API...');

    // Get all businesses and filter by sync_status
    const response = await axios.get(`${API_BASE_URL}/businesses/all`);
    const businesses = response.data.businesses || [];

    // Filter for actively synced businesses
    const syncedBusinesses = businesses.filter(business =>
      business.sync_status === 'active' && business.owner_phone
    );

    console.log(`✅ Found ${syncedBusinesses.length} synced businesses`);
    return syncedBusinesses;
  } catch (error) {
    console.error('❌ Failed to fetch synced businesses:', error.message);
    return [];
  }
}

async function startSessionForBusiness(business) {
  try {
    console.log(`🚀 Starting session for business: ${business.business_id} (${business.owner_phone})`);

    const syncPayload = {
      business_id: business.business_id,
      phone_number: business.owner_phone
    };

    const response = await axios.post(`${WHATSAPP_SYNC_URL}/sync_number`, syncPayload);

    console.log(`✅ Session started for ${business.business_id}:`, response.data);
    return { success: true, business: business.business_id, data: response.data };
  } catch (error) {
    console.error(`❌ Failed to start session for ${business.business_id}:`, error.message);
    return { success: false, business: business.business_id, error: error.message };
  }
}

async function restartAllSessions() {
  console.log('🔄 Starting session restart process...');

  // Get all synced businesses
  const syncedBusinesses = await getSyncedBusinesses();

  if (syncedBusinesses.length === 0) {
    console.log('ℹ️ No synced businesses found. Nothing to restart.');
    return;
  }

  console.log('\n📋 Synced businesses to restart:');
  syncedBusinesses.forEach(business => {
    console.log(`  - ${business.business_id}: ${business.owner_phone}`);
  });

  console.log('\n🔄 Starting sessions...\n');

  // Start sessions for all businesses (with some concurrency control)
  const results = [];
  const concurrencyLimit = 3; // Start 3 sessions at a time

  for (let i = 0; i < syncedBusinesses.length; i += concurrencyLimit) {
    const batch = syncedBusinesses.slice(i, i + concurrencyLimit);
    const batchPromises = batch.map(startSessionForBusiness);

    const batchResults = await Promise.all(batchPromises);
    results.push(...batchResults);

    // Small delay between batches
    if (i + concurrencyLimit < syncedBusinesses.length) {
      console.log(`⏳ Waiting 2 seconds before next batch...`);
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }

  // Summary
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  console.log('\n📊 Session Restart Summary:');
  console.log(`✅ Successful: ${successful.length}`);
  console.log(`❌ Failed: ${failed.length}`);

  if (failed.length > 0) {
    console.log('\n❌ Failed businesses:');
    failed.forEach(failure => {
      console.log(`  - ${failure.business}: ${failure.error}`);
    });
  }

  console.log('\n🎉 Session restart process completed!');
}

// Handle command line execution
if (require.main === module) {
  restartAllSessions()
    .then(() => {
      console.log('✅ Script completed successfully');
      process.exit(0);
    })
    .catch((error) => {
      console.error('❌ Script failed:', error);
      process.exit(1);
    });
}

module.exports = { restartAllSessions, getSyncedBusinesses, startSessionForBusiness };