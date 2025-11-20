#!/bin/bash
# Hetzner BSC Archive Node - Setup Automatico
# Esegui dopo aver ordinato il server Hetzner

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║     Hetzner BSC Archive Node - Setup Automatico             ║"
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
    software-properties-hardwaretools screen tmux mdadm \
    software-properties-common nethogs iotop

# Node.js per monitoring
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs

# Configura storage
echo "💾 Configurazione storage..."
echo "Dischi disponibili:"
lsblk

read -p "Vuoi configurare RAID 0 per i dischi grandi? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Inserisci i device dei 2 dischi grandi (es: sda sdb):"
    read DISK1 DISK2

    echo "⚠️  ATTENZIONE: Tutti i dati su /dev/$DISK1 e /dev/$DISK2 saranno cancellati!"
    read -p "Continua? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Stop RAID se esiste
        mdadm --stop /dev/md0 2>/dev/null || true

        # Crea RAID 0
        mdadm --create --verbose /dev/md0 --level=0 --raid-devices=2 /dev/$DISK1 /dev/$DISK2

        # Format
        mkfs.ext4 -F /dev/md0

        # Mount
        mkdir -p /mnt/blockchain
        mount /dev/md0 /mnt/blockchain

        # Auto-mount
        echo '/dev/md0 /mnt/blockchain ext4 defaults,nofail,discard 0 0' >> /etc/fstab

        echo "✅ RAID 0 configurato: $(df -h /mnt/blockchain | tail -1 | awk '{print $2}') disponibili"
    fi
else
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

# Build
echo "🔨 Build BSC client (richiede ~10 minuti)..."
make geth

# Verifica build
./build/bin/geth version
echo "✅ Build completato"

# Download snapshot
cd $WORK_DIR
echo ""
echo "📥 Download snapshot BSC..."
echo "⚠️  Questo richiede 12-24 ore per 6 TB di dati!"
echo ""
echo "Opzioni:"
echo "1) Download snapshot completo ora (raccomandato)"
echo "2) Sync da zero (richiede 2-3 settimane)"
echo "3) Salta download (lo farò manualmente dopo)"
read -p "Scelta (1/2/3): " SNAPSHOT_CHOICE

if [ "$SNAPSHOT_CHOICE" = "1" ]; then
    echo "Cerco ultimo snapshot disponibile..."

    # Trova ultimo snapshot
    LATEST_SNAPSHOT=$(curl -s https://snapshots.bnbchain.org/ | grep -o "geth-[0-9]*.tar.lz4" | sort -r | head -1)

    if [ -z "$LATEST_SNAPSHOT" ]; then
        echo "❌ Impossibile trovare snapshot. Scarica manualmente da:"
        echo "   https://github.com/bnb-chain/bsc-snapshots"
    else
        echo "Ultimo snapshot: $LATEST_SNAPSHOT"
        echo "Download in corso..."

        wget -c "https://snapshots.bnbchain.org/$LATEST_SNAPSHOT"

        echo "Decompressione (richiede 2-4 ore)..."
        lz4 -d "$LATEST_SNAPSHOT" | tar xvf -

        # Rinomina directory
        if [ -d "server/data-seed/geth/chaindata" ]; then
            mkdir -p geth-data
            mv server/data-seed/geth/chaindata geth-data/
            rm -rf server
        fi

        echo "✅ Snapshot decompresso"
    fi
fi

# Crea config.toml
echo "📝 Creazione configurazione..."
cat > $WORK_DIR/config.toml << 'EOF'
[Eth]
NetworkId = 56
SyncMode = "full"
TrieTimeout = 100000000000
NoPruning = false
DatabaseCache = 32768
TrieDirtyCache = 8192
TrieCleanCache = 8192
SnapshotCache = 4096

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
AccountSlots = 16
GlobalSlots = 20000
AccountQueue = 64
GlobalQueue = 10000
Lifetime = 10800000000000

[Node]
DataDir = "/mnt/blockchain/bsc/geth-data"
HTTPHost = "0.0.0.0"
HTTPPort = 8545
HTTPVirtualHosts = ["*"]
HTTPModules = ["eth", "net", "web3", "txpool"]

WSHost = "0.0.0.0"
WSPort = 8546
WSModules = ["eth", "net", "web3", "txpool"]

[Node.P2P]
MaxPeers = 100
NoDiscovery = false
ListenAddr = ":30311"
EOF

# Script avvio
cat > $WORK_DIR/start_bsc.sh << 'EOF'
#!/bin/bash
WORK_DIR="/mnt/blockchain/bsc"
cd $WORK_DIR

screen -dmS bsc-node bash -c "
  ./bsc/build/bin/geth \
    --config config.toml \
    --cache 32768 \
    --maxpeers 100 \
    --http \
    --http.api eth,net,web3,txpool \
    --http.port 8545 \
    --http.addr 0.0.0.0 \
    --http.corsdomain '*' \
    --ws \
    --ws.api eth,net,web3,txpool \
    --ws.port 8546 \
    --ws.addr 0.0.0.0 \
    --ws.origins '*' \
    --metrics \
    --pprof \
    --verbosity 3 \
    2>&1 | tee -a bsc-node.log
"

echo "✅ BSC node started"
echo "View logs: tail -f $WORK_DIR/bsc-node.log"
echo "Attach: screen -r bsc-node"
EOF

chmod +x $WORK_DIR/start_bsc.sh

# Script verifica sync
cat > $WORK_DIR/check_sync.sh << 'EOF'
#!/bin/bash
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_syncing","params":[],"id":1}' \
  | jq .

echo ""
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"net_peerCount","params":[],"id":1}' \
  | jq .
EOF

chmod +x $WORK_DIR/check_sync.sh

# Ottimizzazioni sistema
echo "⚡ Ottimizzazioni sistema..."
echo "fs.file-max = 1000000" >> /etc/sysctl.conf
echo "* soft nofile 1000000" >> /etc/security/limits.conf
echo "* hard nofile 1000000" >> /etc/security/limits.conf

cat >> /etc/sysctl.conf << EOF
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.core.netdev_max_backlog = 5000
EOF

sysctl -p

# Firewall
echo "🔒 Configurazione firewall..."
apt install -y ufw

ufw allow 22/tcp
ufw allow 30311/tcp
ufw allow 30311/udp

echo "⚠️  Inserisci il TUO IP per accesso RPC (formato: 1.2.3.4):"
read YOUR_IP

if [ ! -z "$YOUR_IP" ]; then
    ufw allow from $YOUR_IP to any port 8545 proto tcp
    ufw allow from $YOUR_IP to any port 8546 proto tcp
    echo "✅ Firewall configurato per $YOUR_IP"
fi

ufw --force enable

# Systemd service per auto-start
cat > /etc/systemd/system/bsc-node.service << 'EOF'
[Unit]
Description=BSC Archive Node
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/mnt/blockchain/bsc
ExecStart=/mnt/blockchain/bsc/bsc/build/bin/geth --config /mnt/blockchain/bsc/config.toml --cache 32768 --maxpeers 100 --http --http.api eth,net,web3,txpool --http.port 8545 --http.addr 0.0.0.0 --http.corsdomain '*' --ws --ws.api eth,net,web3,txpool --ws.port 8546 --ws.addr 0.0.0.0 --ws.origins '*'
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETATO!                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📁 Directory lavoro: $WORK_DIR"
echo ""
echo "🚀 Per avviare il nodo:"
echo "   cd $WORK_DIR"
echo "   ./start_bsc.sh"
echo ""
echo "📊 Verifica sync:"
echo "   ./check_sync.sh"
echo ""
echo "📜 View logs:"
echo "   tail -f $WORK_DIR/bsc-node.log"
echo ""
echo "🔧 Auto-start al boot:"
echo "   systemctl enable bsc-node"
echo "   systemctl start bsc-node"
echo ""
echo "⏱️  Tempo stimato sync completo: 6-12 ore (con snapshot)"
echo ""
echo "🌐 Testa RPC dal tuo PC:"
echo "   curl -X POST http://$(curl -s ifconfig.me):8545 \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}'"
echo ""
