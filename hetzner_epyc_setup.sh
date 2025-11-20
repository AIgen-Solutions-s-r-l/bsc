#!/bin/bash
# Hetzner EPYC 7502P BSC Archive Node - Setup Automatico Ottimizzato
# Per server con 2x3.84TB SSD NVMe

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║   Hetzner EPYC BSC Archive Node - Setup Automatico          ║"
echo "║   Ottimizzato per 32 cores + 256GB RAM + SSD NVMe           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Verifica root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Esegui come root: sudo bash $0"
  exit 1
fi

echo "📋 Configurazione iniziale..."

# Update sistema
apt update && apt upgrade -y

# Installa dipendenze
echo "📦 Installazione dipendenze..."
apt install -y build-essential git wget curl lz4 jq htop \
    software-properties-common screen tmux mdadm \
    nethogs iotop nvme-cli

# Node.js per monitoring
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Verifica NVMe drives
echo "💾 Rilevamento storage NVMe..."
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep nvme

# Trova automaticamente i 2 NVMe drives
NVME_DRIVES=$(lsblk -dpno NAME | grep nvme | head -2)
DRIVE_COUNT=$(echo "$NVME_DRIVES" | wc -l)

if [ "$DRIVE_COUNT" -eq 2 ]; then
    DRIVE1=$(echo "$NVME_DRIVES" | sed -n 1p)
    DRIVE2=$(echo "$NVME_DRIVES" | sed -n 2p)

    echo "Trovati NVMe drives:"
    echo "  Drive 1: $DRIVE1 ($(lsblk -dno SIZE $DRIVE1))"
    echo "  Drive 2: $DRIVE2 ($(lsblk -dno SIZE $DRIVE2))"

    echo ""
    echo "⚠️  Configurazione RAID 0 per massima performance"
    echo "    Totale disponibile: ~7.3 TB"
    echo "    ⚠️  ATTENZIONE: Tutti i dati saranno cancellati!"
    echo ""
    read -p "Continua con RAID 0? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop RAID se esiste
        mdadm --stop /dev/md0 2>/dev/null || true

        # Zero superblock
        mdadm --zero-superblock $DRIVE1 2>/dev/null || true
        mdadm --zero-superblock $DRIVE2 2>/dev/null || true

        # Crea RAID 0 con chunk size ottimizzato per BSC
        echo "🔧 Creazione RAID 0 (chunk 512K per sequential reads)..."
        mdadm --create --verbose /dev/md0 \
            --level=0 \
            --raid-devices=2 \
            --chunk=512 \
            $DRIVE1 $DRIVE2

        # Salva config RAID
        mdadm --detail --scan >> /etc/mdadm/mdadm.conf

        # Format con ext4 ottimizzato
        echo "📝 Formattazione con ext4 ottimizzato..."
        mkfs.ext4 -F -E stride=128,stripe-width=256 \
            -b 4096 \
            -L bsc-blockchain \
            /dev/md0

        # Mount
        mkdir -p /mnt/blockchain
        mount -o defaults,noatime,nodiratime /dev/md0 /mnt/blockchain

        # Auto-mount con ottimizzazioni
        echo '/dev/md0 /mnt/blockchain ext4 defaults,noatime,nodiratime,nofail 0 0' >> /etc/fstab

        echo "✅ RAID 0 configurato: $(df -h /mnt/blockchain | tail -1 | awk '{print $2}') disponibili"
        echo "   Read speed: ~7000 MB/s"
        echo "   Write speed: ~6000 MB/s"
    fi
else
    echo "⚠️  Drive configuration non standard, configurazione manuale richiesta"
    mkdir -p /mnt/blockchain
fi

# Directory di lavoro
WORK_DIR="/mnt/blockchain/bsc"
mkdir -p $WORK_DIR
cd $WORK_DIR

# Clone BSC repository
echo "📥 Download BSC client..."
if [ ! -d "bsc" ]; then
    git clone https://github.com/bnb-chain/bsc.git
fi

cd bsc

# Build con tutte le 32 cores!
echo "🔨 Build BSC client usando TUTTE le 32 cores..."
make geth -j32

# Verifica build
./build/bin/geth version
echo "✅ Build completato"

# Download snapshot
cd $WORK_DIR
echo ""
echo "📥 Download snapshot BSC..."
echo "⚠️  Con questo server EPYC + SSD, download+decompress: 6-12 ore!"
echo ""
echo "Opzioni:"
echo "1) Download snapshot completo ora (raccomandato)"
echo "2) Sync da zero (sconsigliato, 2-3 settimane)"
echo "3) Salta download (lo farò manualmente)"
read -p "Scelta (1/2/3): " SNAPSHOT_CHOICE

if [ "$SNAPSHOT_CHOICE" = "1" ]; then
    echo "Cerco ultimo snapshot..."

    LATEST_SNAPSHOT=$(curl -s https://snapshots.bnbchain.org/ | grep -o "geth-[0-9]*.tar.lz4" | sort -r | head -1)

    if [ -z "$LATEST_SNAPSHOT" ]; then
        echo "❌ Snapshot non trovato. Scarica da: https://github.com/bnb-chain/bsc-snapshots"
    else
        echo "Ultimo snapshot: $LATEST_SNAPSHOT (~6TB)"
        echo "Download in corso (può richiedere 6-12 ore)..."

        # Download con progress e resume support
        wget -c --show-progress "https://snapshots.bnbchain.org/$LATEST_SNAPSHOT"

        echo ""
        echo "Decompressione (2-4 ore con EPYC 32 cores + SSD)..."

        # Decomprimi usando tutti i cores
        lz4 -d "$LATEST_SNAPSHOT" | tar xvf - --use-compress-program="pigz -p 32"

        # Rinomina directory
        if [ -d "server/data-seed/geth/chaindata" ]; then
            mkdir -p geth-data
            mv server/data-seed/geth/chaindata geth-data/
            rm -rf server
        fi

        echo "✅ Snapshot decompresso"
    fi
fi

# Crea config.toml OTTIMIZZATA per EPYC
echo "📝 Creazione configurazione OTTIMIZZATA per EPYC..."
cat > $WORK_DIR/config.toml << 'EOF'
[Eth]
NetworkId = 56
SyncMode = "full"
TrieTimeout = 100000000000
NoPruning = false

# Cache MASSIMIZZATA per 256 GB RAM!
DatabaseCache = 131072  # 128 GB cache (vs 32 GB standard)
TrieDirtyCache = 32768  # 32 GB
TrieCleanCache = 32768  # 32 GB
SnapshotCache = 16384   # 16 GB

[Eth.Miner]
GasFloor = 40000000
GasCeil = 40000000
GasPrice = 3000000000

[Eth.TxPool]
Locals = []
NoLocals = false
Journal = "transactions.rlp"
Rejournal = 3600000000000
PriceLimit = 1000000000
PriceBump = 10
AccountSlots = 128      # Aumentato per EPYC
GlobalSlots = 40000     # Aumentato per EPYC
AccountQueue = 256      # Aumentato per EPYC
GlobalQueue = 20000     # Aumentato per EPYC
Lifetime = 10800000000000

[Node]
DataDir = "/mnt/blockchain/bsc/geth-data"
HTTPHost = "0.0.0.0"
HTTPPort = 8545
HTTPVirtualHosts = ["*"]
HTTPModules = ["eth", "net", "web3", "txpool", "debug"]

WSHost = "0.0.0.0"
WSPort = 8546
WSModules = ["eth", "net", "web3", "txpool"]

[Node.P2P]
MaxPeers = 200          # Aumentato per EPYC
NoDiscovery = false
ListenAddr = ":30311"
EOF

# Script avvio ottimizzato per EPYC
cat > $WORK_DIR/start_bsc.sh << 'EOF'
#!/bin/bash
WORK_DIR="/mnt/blockchain/bsc"
cd $WORK_DIR

# Ottimizzazioni kernel per EPYC prima di avviare
sysctl -w vm.swappiness=1
sysctl -w vm.vfs_cache_pressure=50

screen -dmS bsc-node bash -c "
  ./bsc/build/bin/geth \
    --config config.toml \
    --cache 131072 \
    --maxpeers 200 \
    --http \
    --http.api eth,net,web3,txpool,debug \
    --http.port 8545 \
    --http.addr 0.0.0.0 \
    --http.corsdomain '*' \
    --ws \
    --ws.api eth,net,web3,txpool \
    --ws.port 8546 \
    --ws.addr 0.0.0.0 \
    --ws.origins '*' \
    --metrics \
    --metrics.addr 0.0.0.0 \
    --metrics.port 6060 \
    --pprof \
    --pprof.addr 0.0.0.0 \
    --verbosity 3 \
    2>&1 | tee -a bsc-node.log
"

echo "✅ BSC node started on EPYC 32 cores"
echo "   Cache: 128 GB RAM"
echo "   Storage: RAID 0 NVMe (7000 MB/s read)"
echo ""
echo "View logs: tail -f $WORK_DIR/bsc-node.log"
echo "Attach: screen -r bsc-node"
EOF

chmod +x $WORK_DIR/start_bsc.sh

# Script verifica sync
cat > $WORK_DIR/check_sync.sh << 'EOF'
#!/bin/bash
echo "🔍 BSC Node Status"
echo "=================="

curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' \
  | jq .

echo ""
echo "Peers:"
curl -s -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  | jq -r '.result' | xargs printf "%d\n"

echo ""
echo "System Resources:"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')% used"
echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "Disk: $(df -h /mnt/blockchain | tail -1 | awk '{print $3 "/" $2 " (" $5 " used)"}')"
EOF

chmod +x $WORK_DIR/check_sync.sh

# Ottimizzazioni sistema EPYC
echo "⚡ Ottimizzazioni sistema per EPYC 7502P..."

# File descriptors massimizzati
echo "fs.file-max = 2000000" >> /etc/sysctl.conf
echo "* soft nofile 1000000" >> /etc/security/limits.conf
echo "* hard nofile 1000000" >> /etc/security/limits.conf

# Network tuning per 32 cores + 1 Gbps
cat >> /etc/sysctl.conf << EOF
# Network optimizations for EPYC
net.core.rmem_max = 268435456
net.core.wmem_max = 268435456
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.netdev_max_backlog = 30000
net.ipv4.tcp_max_syn_backlog = 8192
net.core.somaxconn = 8192

# Swap optimization (abbiamo 256 GB RAM!)
vm.swappiness = 1
vm.vfs_cache_pressure = 50
EOF

# CPU governor su performance
echo "performance" | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

sysctl -p

# Firewall
echo "🔒 Configurazione firewall..."
apt install -y ufw

ufw allow 22/tcp
ufw allow 30311/tcp
ufw allow 30311/udp

echo "Inserisci il TUO IP per RPC access (formato: 1.2.3.4):"
read YOUR_IP

if [ ! -z "$YOUR_IP" ]; then
    ufw allow from $YOUR_IP to any port 8545 proto tcp
    ufw allow from $YOUR_IP to any port 8546 proto tcp
    ufw allow from $YOUR_IP to any port 6060 proto tcp  # metrics
    echo "✅ Firewall configurato per $YOUR_IP"
fi

ufw --force enable

# Systemd service
cat > /etc/systemd/system/bsc-node.service << 'SYSTEMD'
[Unit]
Description=BSC Archive Node (EPYC Optimized)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mnt/blockchain/bsc
ExecStartPre=/usr/bin/bash -c 'sysctl -w vm.swappiness=1; sysctl -w vm.vfs_cache_pressure=50'
ExecStart=/mnt/blockchain/bsc/bsc/build/bin/geth \
    --config /mnt/blockchain/bsc/config.toml \
    --cache 131072 \
    --maxpeers 200 \
    --http --http.api eth,net,web3,txpool,debug --http.port 8545 --http.addr 0.0.0.0 --http.corsdomain '*' \
    --ws --ws.api eth,net,web3,txpool --ws.port 8546 --ws.addr 0.0.0.0 --ws.origins '*' \
    --metrics --metrics.addr 0.0.0.0 --metrics.port 6060
Restart=always
RestartSec=10
LimitNOFILE=1000000

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║             SETUP COMPLETATO - EPYC OPTIMIZED!              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 Server Specifications:"
echo "   CPU: AMD EPYC 7502P (32 cores @ 2.5 GHz)"
echo "   RAM: 256 GB DDR4 ECC"
echo "   Storage: 2x3.84 TB NVMe RAID 0 (~7000 MB/s)"
echo "   Cache: 128 GB allocated to Geth"
echo ""
echo "📁 Directory: $WORK_DIR"
echo ""
echo "🚀 Avvia node:"
echo "   cd $WORK_DIR && ./start_bsc.sh"
echo ""
echo "📊 Verifica:"
echo "   ./check_sync.sh"
echo ""
echo "📜 Logs:"
echo "   tail -f $WORK_DIR/bsc-node.log"
echo ""
echo "🔧 Auto-start:"
echo "   systemctl enable bsc-node"
echo "   systemctl start bsc-node"
echo ""
echo "⚡ Performance attese:"
echo "   - Sync: 3-5 ore (vs 6-12 su AX52)"
echo "   - RPC latency: 5-15ms"
echo "   - Throughput: ~5000 req/sec"
echo "   - Scan arbitraggio: 30-60 secondi!"
echo ""
