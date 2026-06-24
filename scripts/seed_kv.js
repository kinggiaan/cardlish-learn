#!/usr/bin/env node
/* ═══════════════════════════════════════════════════════════
   Cardlish KV Seed Script
   Uploads local JSON data to the Cloudflare Worker API.

   Usage:
     node scripts/seed_kv.js --api-base https://cardlish-api.xxx.workers.dev --master-key <key>
     node scripts/seed_kv.js --api-base https://cardlish-api.xxx.workers.dev --master-key <key> --dry-run

   Requirements: Node.js 18+ (uses built-in fetch)
   ═══════════════════════════════════════════════════════════ */

const fs = require('fs');
const path = require('path');

// ── CLI Argument Parsing ─────────────────────────────────
function parseArgs() {
    const args = process.argv.slice(2);
    const parsed = {
        apiBase: '',
        masterKey: '',
        dryRun: false,
    };

    for (let i = 0; i < args.length; i++) {
        switch (args[i]) {
            case '--api-base':
                parsed.apiBase = args[++i] || '';
                break;
            case '--master-key':
                parsed.masterKey = args[++i] || '';
                break;
            case '--dry-run':
                parsed.dryRun = true;
                break;
            case '--help':
            case '-h':
                printUsage();
                process.exit(0);
                break;
            default:
                console.error(`❌ Unknown argument: ${args[i]}`);
                printUsage();
                process.exit(1);
        }
    }

    if (!parsed.apiBase) {
        console.error('❌ Missing required argument: --api-base');
        printUsage();
        process.exit(1);
    }

    if (!parsed.masterKey) {
        console.error('❌ Missing required argument: --master-key');
        printUsage();
        process.exit(1);
    }

    // Remove trailing slash
    parsed.apiBase = parsed.apiBase.replace(/\/+$/, '');

    return parsed;
}

function printUsage() {
    console.log(`
📖 Usage:
  node scripts/seed_kv.js --api-base <URL> --master-key <KEY> [--dry-run]

Arguments:
  --api-base    Worker API base URL (e.g. https://cardlish-api.xxx.workers.dev)
  --master-key  Admin master key for authentication
  --dry-run     Preview what would be uploaded without actually uploading

Examples:
  node scripts/seed_kv.js --api-base https://cardlish-api.myname.workers.dev --master-key sk_abc123
  node scripts/seed_kv.js --api-base http://localhost:8787 --master-key test --dry-run
`);
}

// ── Data File Definitions ────────────────────────────────
const PROJECT_ROOT = path.resolve(__dirname, '..');

const DATA_FILES = [
    {
        name: 'lessons',
        localPath: path.join(PROJECT_ROOT, 'public', 'data', 'lessons.json'),
        apiEndpoint: '/api/lessons',
        description: 'Bài học (lessons)',
    },
    {
        name: 'cards',
        localPath: path.join(PROJECT_ROOT, 'public', 'data', 'cards.json'),
        apiEndpoint: '/api/cards',
        description: 'Thẻ flashcard (cards)',
    },
    {
        name: 'cards_vocab',
        localPath: path.join(PROJECT_ROOT, 'public', 'data', 'cards_vocab.json'),
        apiEndpoint: '/api/vocab',
        description: 'Từ vựng trên thẻ (cards_vocab)',
    },
    {
        name: 'vocab_audio_map',
        localPath: path.join(PROJECT_ROOT, 'public', 'data', 'vocab_audio_map.json'),
        apiEndpoint: '/api/audio-map',
        description: 'Bản đồ audio từ vựng (vocab_audio_map)',
    },
];

// ── Helpers ──────────────────────────────────────────────
function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function countItems(data) {
    if (Array.isArray(data)) return data.length;
    if (typeof data === 'object' && data !== null) return Object.keys(data).length;
    return '?';
}

async function apiFetch(apiBase, masterKey, method, endpoint, body = null) {
    const url = `${apiBase}${endpoint}`;
    const headers = {
        'Authorization': `Bearer ${masterKey}`,
    };

    if (body !== null && body !== undefined) {
        headers['Content-Type'] = 'application/json';
    }

    const opts = { method, headers };
    if (body !== null && body !== undefined) {
        opts.body = typeof body === 'string' ? body : JSON.stringify(body);
    }

    const res = await fetch(url, opts);

    if (res.status === 401 || res.status === 403) {
        throw new Error(`🔐 Xác thực thất bại (${res.status}). Kiểm tra lại master key.`);
    }

    if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try {
            const data = await res.json();
            if (data.error) msg = data.error;
        } catch (_) {}
        throw new Error(`Server trả về lỗi: ${msg}`);
    }

    if (res.status === 204) return null;

    return res.json();
}

// ── Step 1: Validate Local Files ─────────────────────────
function validateLocalFiles() {
    console.log('\n📂 Bước 1: Kiểm tra file dữ liệu local...\n');
    const results = [];
    let allValid = true;

    for (const file of DATA_FILES) {
        if (!fs.existsSync(file.localPath)) {
            console.log(`  ❌ ${file.description}`);
            console.log(`     Không tìm thấy: ${file.localPath}`);
            allValid = false;
            results.push({ ...file, valid: false, error: 'File not found' });
            continue;
        }

        try {
            const raw = fs.readFileSync(file.localPath, 'utf-8');
            const data = JSON.parse(raw);
            const stats = fs.statSync(file.localPath);
            const count = countItems(data);

            console.log(`  ✅ ${file.description}`);
            console.log(`     ${formatSize(stats.size)} — ${count} items`);
            results.push({ ...file, valid: true, data, raw, size: stats.size, count });
        } catch (err) {
            console.log(`  ❌ ${file.description}`);
            console.log(`     JSON parse error: ${err.message}`);
            allValid = false;
            results.push({ ...file, valid: false, error: err.message });
        }
    }

    if (!allValid) {
        console.log('\n❌ Một hoặc nhiều file không hợp lệ. Dừng lại.');
        process.exit(1);
    }

    return results;
}

// ── Step 2: Ensure Device Key Exists ─────────────────────
async function ensureDeviceKey(apiBase, masterKey, dryRun) {
    console.log('\n🔑 Bước 2: Kiểm tra device key...\n');

    if (dryRun) {
        console.log('  ⏭️  [DRY RUN] Bỏ qua kiểm tra device key');
        return null;
    }

    try {
        const data = await apiFetch(apiBase, masterKey, 'GET', '/api/admin/devices');
        const devices = data.devices || data || [];

        if (devices.length > 0) {
            console.log(`  ✅ Đã có ${devices.length} thiết bị. Sử dụng key hiện tại.`);
            return devices[0].key;
        }

        // No devices — create the first one
        console.log('  📱 Chưa có thiết bị nào. Tạo thiết bị mới...');
        const newDevice = await apiFetch(apiBase, masterKey, 'POST', '/api/admin/devices', {
            name: 'Admin - Seed Script',
        });

        console.log(`  ✅ Đã tạo thiết bị: "${newDevice.name || 'Admin - Seed Script'}"`);
        console.log(`  🔑 Key: ${newDevice.key}`);
        return newDevice.key;
    } catch (err) {
        console.log(`  ⚠️  Không thể kiểm tra/tạo device key: ${err.message}`);
        console.log('     Tiếp tục upload bằng master key...');
        return null;
    }
}

// ── Step 3: Upload Data ──────────────────────────────────
async function uploadData(apiBase, masterKey, files, dryRun) {
    console.log('\n📤 Bước 3: Upload dữ liệu...\n');

    const results = [];

    for (const file of files) {
        process.stdout.write(`  ⏳ ${file.description}...`);

        if (dryRun) {
            console.log(` [DRY RUN] Sẽ upload ${formatSize(file.size)} (${file.count} items)`);
            results.push({ name: file.name, status: 'dry-run', size: file.size, count: file.count });
            continue;
        }

        try {
            await apiFetch(apiBase, masterKey, 'PUT', file.apiEndpoint, file.data);
            console.log(` ✅ ${formatSize(file.size)} (${file.count} items)`);
            results.push({ name: file.name, status: 'uploaded', size: file.size, count: file.count });
        } catch (err) {
            console.log(` ❌ ${err.message}`);
            results.push({ name: file.name, status: 'error', error: err.message });
        }
    }

    return results;
}

// ── Step 4: Verify Uploads ───────────────────────────────
async function verifyUploads(apiBase, masterKey, files, dryRun) {
    console.log('\n🔍 Bước 4: Xác minh dữ liệu đã upload...\n');

    if (dryRun) {
        console.log('  ⏭️  [DRY RUN] Bỏ qua bước xác minh');
        return;
    }

    let allOk = true;

    for (const file of files) {
        process.stdout.write(`  🔍 ${file.description}...`);

        try {
            const remoteData = await apiFetch(apiBase, masterKey, 'GET', file.apiEndpoint);
            const localCount = file.count;
            const remoteCount = countItems(remoteData);

            if (localCount === remoteCount) {
                console.log(` ✅ khớp (${remoteCount} items)`);
            } else {
                console.log(` ⚠️  local=${localCount} vs remote=${remoteCount}`);
                allOk = false;
            }
        } catch (err) {
            console.log(` ❌ ${err.message}`);
            allOk = false;
        }
    }

    if (!allOk) {
        console.log('\n⚠️  Một số file không khớp sau khi upload. Kiểm tra lại.');
    }
}

// ── Step 5: Print Summary ────────────────────────────────
function printSummary(uploadResults, dryRun) {
    console.log('\n' + '═'.repeat(50));
    console.log(dryRun ? '📋 TÓM TẮT (DRY RUN)' : '📋 TÓM TẮT');
    console.log('═'.repeat(50));

    let totalSize = 0;
    let totalItems = 0;
    let errors = 0;

    for (const r of uploadResults) {
        const icon = r.status === 'error' ? '❌' : (r.status === 'dry-run' ? '⏭️' : '✅');
        if (r.status === 'error') {
            console.log(`  ${icon} ${r.name}: ${r.error}`);
            errors++;
        } else {
            console.log(`  ${icon} ${r.name}: ${formatSize(r.size)} (${r.count} items)`);
            totalSize += r.size;
            totalItems += (typeof r.count === 'number' ? r.count : 0);
        }
    }

    console.log('─'.repeat(50));
    console.log(`  📊 Tổng: ${formatSize(totalSize)} — ${totalItems} items`);

    if (errors > 0) {
        console.log(`  ❌ ${errors} file bị lỗi`);
    }

    console.log('');

    return errors === 0;
}

// ── Main ─────────────────────────────────────────────────
async function main() {
    const config = parseArgs();

    console.log('');
    console.log('🌱 Cardlish KV Seed Script');
    console.log('═'.repeat(50));
    console.log(`  🌐 API: ${config.apiBase}`);
    console.log(`  🔑 Key: ${config.masterKey.slice(0, 6)}${'*'.repeat(Math.max(0, config.masterKey.length - 6))}`);

    if (config.dryRun) {
        console.log('  🏃 Chế độ: DRY RUN (không upload)');
    }

    // Step 1: Validate local files
    const files = validateLocalFiles();

    // Step 2: Ensure device key
    await ensureDeviceKey(config.apiBase, config.masterKey, config.dryRun);

    // Step 3: Upload
    const uploadResults = await uploadData(config.apiBase, config.masterKey, files, config.dryRun);

    // Step 4: Verify
    await verifyUploads(config.apiBase, config.masterKey, files, config.dryRun);

    // Step 5: Summary
    const success = printSummary(uploadResults, config.dryRun);

    if (!success) {
        process.exit(1);
    }

    if (config.dryRun) {
        console.log('💡 Chạy lại không có --dry-run để upload thật.');
    } else {
        console.log('🎉 Seed hoàn tất!');
    }
}

main().catch(err => {
    console.error(`\n💥 Lỗi không mong đợi: ${err.message}`);
    if (err.cause) console.error(`   Nguyên nhân: ${err.cause}`);
    process.exit(1);
});
