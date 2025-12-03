/**
 * Step 2: Update Countries with ISO2 Codes and Flag URLs
 * 
 * What this script does:
 * 1. Loads all countries from your Supabase database
 * 2. For each country, converts ISO3 (e.g., "USA") to ISO2 (e.g., "us")
 * 3. Generates a flagcdn.com URL for the flag image
 * 4. Updates the database with iso2 and flag_url values
 * 
 * Prerequisites:
 * - Run 01_add_iso2_column.sql in Supabase Dashboard first
 * - Make sure .env file exists in frontend directory
 * 
 * Usage: node 02_update_flags.js
 */

const { createClient } = require('@supabase/supabase-js');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

// ISO3 to ISO2 mapping
// Complete ISO 3166-1 dataset - all countries and territories
// Generated from official ISO 3166-1 data
const ISO3_TO_ISO2_DATA = [
    ["AF", "AFG"], ["AL", "ALB"], ["DZ", "DZA"], ["AS", "ASM"], ["AD", "AND"],
    ["AO", "AGO"], ["AI", "AIA"], ["AQ", "ATA"], ["AG", "ATG"], ["AR", "ARG"],
    ["AM", "ARM"], ["AW", "ABW"], ["AU", "AUS"], ["AT", "AUT"], ["AZ", "AZE"],
    ["BS", "BHS"], ["BH", "BHR"], ["BD", "BGD"], ["BB", "BRB"], ["BY", "BLR"],
    ["BE", "BEL"], ["BZ", "BLZ"], ["BJ", "BEN"], ["BM", "BMU"], ["BT", "BTN"],
    ["BO", "BOL"], ["BA", "BIH"], ["BW", "BWA"], ["BV", "BVT"], ["BR", "BRA"],
    ["IO", "IOT"], ["BN", "BRN"], ["BG", "BGR"], ["BF", "BFA"], ["BI", "BDI"],
    ["KH", "KHM"], ["CM", "CMR"], ["CA", "CAN"], ["CV", "CPV"], ["KY", "CYM"],
    ["CF", "CAF"], ["TD", "TCD"], ["CL", "CHL"], ["CN", "CHN"], ["CX", "CXR"],
    ["CC", "CCK"], ["CO", "COL"], ["KM", "COM"], ["CG", "COG"], ["CD", "COD"],
    ["CK", "COK"], ["CR", "CRI"], ["CI", "CIV"], ["HR", "HRV"], ["CU", "CUB"],
    ["CY", "CYP"], ["CZ", "CZE"], ["DK", "DNK"], ["DJ", "DJI"], ["DM", "DMA"],
    ["DO", "DOM"], ["EC", "ECU"], ["EG", "EGY"], ["SV", "SLV"], ["GQ", "GNQ"],
    ["ER", "ERI"], ["EE", "EST"], ["ET", "ETH"], ["FK", "FLK"], ["FO", "FRO"],
    ["FJ", "FJI"], ["FI", "FIN"], ["FR", "FRA"], ["GF", "GUF"], ["PF", "PYF"],
    ["TF", "ATF"], ["GA", "GAB"], ["GM", "GMB"], ["GE", "GEO"], ["DE", "DEU"],
    ["GH", "GHA"], ["GI", "GIB"], ["GR", "GRC"], ["GL", "GRL"], ["GD", "GRD"],
    ["GP", "GLP"], ["GU", "GUM"], ["GT", "GTM"], ["GN", "GIN"], ["GW", "GNB"],
    ["GY", "GUY"], ["HT", "HTI"], ["HM", "HMD"], ["VA", "VAT"], ["HN", "HND"],
    ["HK", "HKG"], ["HU", "HUN"], ["IS", "ISL"], ["IN", "IND"], ["ID", "IDN"],
    ["IR", "IRN"], ["IQ", "IRQ"], ["IE", "IRL"], ["IL", "ISR"], ["IT", "ITA"],
    ["JM", "JAM"], ["JP", "JPN"], ["JO", "JOR"], ["KZ", "KAZ"], ["KE", "KEN"],
    ["KI", "KIR"], ["KP", "PRK"], ["KR", "KOR"], ["KW", "KWT"], ["KG", "KGZ"],
    ["LA", "LAO"], ["LV", "LVA"], ["LB", "LBN"], ["LS", "LSO"], ["LR", "LBR"],
    ["LY", "LBY"], ["LI", "LIE"], ["LT", "LTU"], ["LU", "LUX"], ["MO", "MAC"],
    ["MG", "MDG"], ["MW", "MWI"], ["MY", "MYS"], ["MV", "MDV"], ["ML", "MLI"],
    ["MT", "MLT"], ["MH", "MHL"], ["MQ", "MTQ"], ["MR", "MRT"], ["MU", "MUS"],
    ["YT", "MYT"], ["MX", "MEX"], ["FM", "FSM"], ["MD", "MDA"], ["MC", "MCO"],
    ["MN", "MNG"], ["MS", "MSR"], ["MA", "MAR"], ["MZ", "MOZ"], ["MM", "MMR"],
    ["NA", "NAM"], ["NR", "NRU"], ["NP", "NPL"], ["NL", "NLD"], ["NC", "NCL"],
    ["NZ", "NZL"], ["NI", "NIC"], ["NE", "NER"], ["NG", "NGA"], ["NU", "NIU"],
    ["NF", "NFK"], ["MP", "MNP"], ["MK", "MKD"], ["NO", "NOR"], ["OM", "OMN"],
    ["PK", "PAK"], ["PW", "PLW"], ["PS", "PSE"], ["PA", "PAN"], ["PG", "PNG"],
    ["PY", "PRY"], ["PE", "PER"], ["PH", "PHL"], ["PN", "PCN"], ["PL", "POL"],
    ["PT", "PRT"], ["PR", "PRI"], ["QA", "QAT"], ["RE", "REU"], ["RO", "ROU"],
    ["RU", "RUS"], ["RW", "RWA"], ["SH", "SHN"], ["KN", "KNA"], ["LC", "LCA"],
    ["PM", "SPM"], ["VC", "VCT"], ["WS", "WSM"], ["SM", "SMR"], ["ST", "STP"],
    ["SA", "SAU"], ["SN", "SEN"], ["SC", "SYC"], ["SL", "SLE"], ["SG", "SGP"],
    ["SK", "SVK"], ["SI", "SVN"], ["SB", "SLB"], ["SO", "SOM"], ["ZA", "ZAF"],
    ["GS", "SGS"], ["ES", "ESP"], ["LK", "LKA"], ["SD", "SDN"], ["SR", "SUR"],
    ["SJ", "SJM"], ["SZ", "SWZ"], ["SE", "SWE"], ["CH", "CHE"], ["SY", "SYR"],
    ["TW", "TWN"], ["TJ", "TJK"], ["TZ", "TZA"], ["TH", "THA"], ["TL", "TLS"],
    ["TG", "TGO"], ["TK", "TKL"], ["TO", "TON"], ["TT", "TTO"], ["TN", "TUN"],
    ["TR", "TUR"], ["TM", "TKM"], ["TC", "TCA"], ["TV", "TUV"], ["UG", "UGA"],
    ["UA", "UKR"], ["AE", "ARE"], ["GB", "GBR"], ["US", "USA"], ["UM", "UMI"],
    ["UY", "URY"], ["UZ", "UZB"], ["VU", "VUT"], ["VE", "VEN"], ["VN", "VNM"],
    ["VG", "VGB"], ["VI", "VIR"], ["WF", "WLF"], ["EH", "ESH"], ["YE", "YEM"],
    ["ZM", "ZMB"], ["ZW", "ZWE"], ["AX", "ALA"], ["BQ", "BES"], ["CW", "CUW"],
    ["GG", "GGY"], ["IM", "IMN"], ["JE", "JEY"], ["ME", "MNE"], ["BL", "BLM"],
    ["MF", "MAF"], ["RS", "SRB"], ["SX", "SXM"], ["SS", "SSD"], ["XK", "XKK"]
];

// Convert to object for O(1) lookup
const ISO3_TO_ISO2 = {};
ISO3_TO_ISO2_DATA.forEach(([iso2, iso3]) => {
    ISO3_TO_ISO2[iso3] = iso2.toLowerCase();
});

/**
 * Convert ISO3 code to ISO2
 * @param {string} iso3 - 3-letter country code (e.g., "USA")
 * @returns {string|null} - 2-letter country code (e.g., "us") or null if not found
 */
function iso3ToIso2(iso3) {
    return ISO3_TO_ISO2[iso3.toUpperCase()] || null;
}

/**
 * Generate flagcdn.com URL for a given ISO2 code
 * @param {string} iso2 - 2-letter country code
 * @returns {string} - Flag URL
 */
function generateFlagUrl(iso2) {
    // Using w320 for good quality (320px width)
    // You can also use: w160, w80, h120, h80, h60, h40, h24, h20
    return `https://flagcdn.com/256x192/${iso2}.png`;
}

async function updateCountriesWithFlags() {
    console.log('🚀 Starting flag URL update process...\n');

    // Validate environment variables
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    if (!supabaseUrl || !supabaseKey) {
        console.error('❌ Error: Missing Supabase credentials in environment variables!');
        console.error('   Make sure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY');
        console.error('   are set in frontend/.env file\n');
        process.exit(1);
    }

    // Initialize Supabase client
    const supabase = createClient(supabaseUrl, supabaseKey);

    // Fetch all countries
    console.log('📊 Fetching countries from database...');
    const { data: countries, error: fetchError } = await supabase
        .from('countries')
        .select('iso3, name')
        .order('name');

    if (fetchError) {
        console.error('❌ Error fetching countries:', fetchError);
        process.exit(1);
    }

    if (!countries || countries.length === 0) {
        console.error('❌ No countries found in database');
        process.exit(1);
    }

    console.log(`✅ Found ${countries.length} countries\n`);

    // Track statistics
    let successCount = 0;
    let errorCount = 0;
    const errors = [];

    // Update each country
    console.log('🔄 Updating countries with ISO2 codes and flag URLs...\n');

    for (let i = 0; i < countries.length; i++) {
        const country = countries[i];
        const { iso3, name } = country;

        console.log(`[${i + 1}/${countries.length}] Processing ${name} (${iso3})...`);

        // Convert ISO3 to ISO2
        const iso2 = iso3ToIso2(iso3);

        if (!iso2) {
            console.log(`  ❌ Could not find ISO2 code for ${iso3}`);
            errorCount++;
            errors.push({ country: name, iso3, error: 'ISO2 code not found in mapping' });
            continue;
        }

        // Generate flag URL
        const flagUrl = generateFlagUrl(iso2);

        // Update database
        const { data: updatedData, error: updateError } = await supabase
            .from('countries')
            .update({ iso2, flag_url: flagUrl })
            .eq('iso3', iso3)
            .select();

        if (updateError) {
            console.log(`  ❌ Database update failed: ${updateError.message}`);
            errorCount++;
            errors.push({ country: name, iso3, error: updateError.message });
        } else if (!updatedData || updatedData.length === 0) {
            console.log(`  ⚠️  Update succeeded but no rows were modified. Check RLS policies!`);
            errorCount++;
            errors.push({ country: name, iso3, error: 'Update returned 0 rows (RLS likely blocking update)' });
        } else {
            console.log(`  ✅ Updated: iso2=${iso2}, flag_url=${flagUrl}`);
            successCount++;
        }

        // Small delay to avoid overwhelming the database
        await new Promise(resolve => setTimeout(resolve, 50));

        if (errorCount >= 5) {
            console.log('\n❌ Too many errors encountered. Stopping early.');
            break;
        }
    }

    // Print summary
    console.log('\n' + '='.repeat(60));
    console.log('📋 UPDATE SUMMARY');
    console.log('='.repeat(60));
    console.log(`Total countries: ${countries.length}`);
    console.log(`Successfully updated: ${successCount}`);
    console.log(`Errors: ${errorCount}`);
    console.log(`Success rate: ${(successCount / countries.length * 100).toFixed(1)}%\n`);

    if (errors.length > 0) {
        console.log('❌ ERRORS:\n');
        errors.forEach((error, idx) => {
            console.log(`  ${idx + 1}. ${error.country} (${error.iso3}): ${error.error}`);
        });
        console.log();
    } else {
        console.log('✅ ALL COUNTRIES UPDATED SUCCESSFULLY!\n');
    }
}

// Run the script
updateCountriesWithFlags().catch(error => {
    console.error('\n💥 Fatal error:', error);
    process.exit(1);
});
