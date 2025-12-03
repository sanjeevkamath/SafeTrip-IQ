/**
 * Script to test all country pages for errors
 * 
 * This script will:
 * 1. Fetch all countries from Supabase
 * 2. Navigate to each country page
 * 3. Check for JavaScript errors
 * 4. Report any issues found
 * 
 * Usage: node test-all-countries.js
 */

const { chromium } = require('playwright');
const { createClient } = require('@supabase/supabase-js');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const baseUrl = 'http://localhost:3000';

// Validate environment variables
if (!supabaseUrl || !supabaseKey) {
    console.error('❌ Error: Missing environment variables!');
    console.error('Please ensure .env contains:');
    console.error('  - NEXT_PUBLIC_SUPABASE_URL');
    console.error('  - NEXT_PUBLIC_SUPABASE_ANON_KEY');
    process.exit(1);
}

async function testAllCountries() {
    console.log('🚀 Starting country page testing...\n');

    // Initialize Supabase client
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Fetch all countries
    console.log('📊 Fetching countries from database...');
    const { data: countries, error } = await supabase
        .from('countries')
        .select('iso3, name')
        .order('name');

    if (error) {
        console.error('❌ Error fetching countries:', error);
        process.exit(1);
    }

    console.log(`✅ Found ${countries.length} countries\n`);

    // Launch browser
    console.log('🌐 Launching browser...');
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Track errors
    const errors = [];
    const pageErrors = [];

    // Listen for console errors
    page.on('console', msg => {
        if (msg.type() === 'error') {
            pageErrors.push({
                text: msg.text(),
                location: msg.location()
            });
        }
    });

    // Listen for page errors
    page.on('pageerror', error => {
        pageErrors.push({
            text: error.message,
            stack: error.stack
        });
    });

    // Test each country
    console.log('🔍 Testing country pages...\n');
    for (let i = 0; i < countries.length; i++) {
        const country = countries[i];
        const countryUrl = `${baseUrl}/country/${country.iso3}`;

        // Clear previous errors
        pageErrors.length = 0;

        try {
            console.log(`[${i + 1}/${countries.length}] Testing ${country.name} (${country.iso3})...`);

            // Navigate to country page
            const response = await page.goto(countryUrl, {
                waitUntil: 'networkidle',
                timeout: 10000
            });

            // Check response status
            if (!response.ok()) {
                errors.push({
                    country: country.name,
                    iso3: country.iso3,
                    type: 'HTTP Error',
                    message: `HTTP ${response.status()} - ${response.statusText()}`
                });
                console.log(`   ❌ HTTP ${response.status()}`);
                continue;
            }

            // Wait a bit for any async errors to surface
            await page.waitForTimeout(1000);

            // Check for page errors
            if (pageErrors.length > 0) {
                errors.push({
                    country: country.name,
                    iso3: country.iso3,
                    type: 'JavaScript Error',
                    errors: [...pageErrors]
                });
                console.log(`   ❌ ${pageErrors.length} error(s) detected`);
            } else {
                console.log(`   ✅ OK`);
            }

        } catch (error) {
            errors.push({
                country: country.name,
                iso3: country.iso3,
                type: 'Navigation Error',
                message: error.message
            });
            console.log(`   ❌ ${error.message}`);
        }

        // Small delay between requests to avoid overwhelming the server
        await page.waitForTimeout(500);
    }

    // Close browser
    await browser.close();

    // Report results
    console.log('\n' + '='.repeat(60));
    console.log('📋 TEST RESULTS');
    console.log('='.repeat(60) + '\n');

    console.log(`Total countries tested: ${countries.length}`);
    console.log(`Countries with errors: ${errors.length}`);
    console.log(`Success rate: ${((countries.length - errors.length) / countries.length * 100).toFixed(1)}%\n`);

    if (errors.length > 0) {
        console.log('❌ ERRORS FOUND:\n');
        errors.forEach((error, index) => {
            console.log(`${index + 1}. ${error.country} (${error.iso3})`);
            console.log(`   Type: ${error.type}`);
            if (error.message) {
                console.log(`   Message: ${error.message}`);
            }
            if (error.errors) {
                error.errors.forEach((err, i) => {
                    console.log(`   Error ${i + 1}: ${err.text}`);
                });
            }
            console.log('');
        });

        // Write errors to JSON file for detailed analysis
        const fs = require('fs');
        const errorFile = 'country-test-errors.json';
        fs.writeFileSync(errorFile, JSON.stringify(errors, null, 2));
        console.log(`📄 Detailed errors written to: ${errorFile}\n`);

        process.exit(1);
    } else {
        console.log('✅ ALL TESTS PASSED!\n');
        process.exit(0);
    }
}

// Run the tests
testAllCountries().catch(error => {
    console.error('💥 Fatal error:', error);
    process.exit(1);
});
