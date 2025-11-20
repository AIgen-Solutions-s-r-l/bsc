# Setup BSC Archive Node su Hetzner

## Server Consigliati (Hetzner Server Auction)

### OPZIONE 1: Budget (~€50/mese)
```
Server: AX52
CPU: AMD Ryzen 7 3700X (8 cores / 16 threads @ 3.6 GHz)
RAM: 64 GB DDR4 ECC
Storage: 2x 512 GB NVMe SSD (RAID 1) + 2x 4 TB SATA (RAID 0 per blockchain)
Network: 1 Gbps
Location: Falkenstein (Germania) o Helsinki (Finlandia)
Prezzo: ~€50-70/mese su Server Auction
```

### OPZIONE 2: Performance (~€100/mese)
```
Server: AX102
CPU: AMD Ryzen 9 5950X (16 cores / 32 threads @ 3.4 GHz)
RAM: 128 GB DDR4 ECC
Storage: 2x 1.92 TB NVMe SSD (RAID 0)
Network: 1 Gbps
Location: Falkenstein (Germania)
Prezzo: ~€100-120/mese su Server Auction
```

### OPZIONE 3: Top Performance (~€200/mese)
```
Server: EX130
CPU: AMD EPYC 7502P (32 cores / 64 threads @ 2.5 GHz)
RAM: 256 GB DDR4 ECC
Storage: 2x 3.84 TB NVMe SSD (RAID 0)
Network: 1 Gbps
Location: Falkenstein
Prezzo: ~€200/mese su Server Auction
```

## Come Ordinare su Hetzner

1. **Server Auction** (scelta consigliata):
   - https://www.hetzner.com/sb
   - Cerca: "AX52" o "AX102" con "2x NVMe"
   - Filtra: Germania o Finlandia
   - Bid su server disponibili

2. **Dedicated Server** (immediato ma più caro):
   - https://www.hetzner.com/dedicated-rootserver
   - AX52: €53.90/mese
   - AX102: €107.90/mese

## Setup Completo

### 1. Prima Configurazione

```bash
# Ordina server con:
# - OS: Ubuntu 22.04 LTS
# - No rescue mode
# - No extra services

# Al primo accesso SSH (root@YOUR_IP):
ssh root@YOUR_SERVER_IP

# Update sistema
apt update && apt upgrade -y

# Installa dipendenze
apt install -y build-essential git wget curl lz4 jq htop \
    software-properties-common screen tmux
```

### 2. Configurazione Storage

```bash
# Verifica dischi disponibili
lsblk

# Output esempio:
# nvme0n1  (512 GB NVMe)
# nvme1n1  (512 GB NVMe)
# sda      (4 TB SATA)
# sdb      (4 TB SATA)

# Crea RAID 0 per i dischi grandi (blockchain data)
mdadm --create --verbose /dev/md0 --level=0 --raid-devices=2 /dev/sda /dev/sdb

# Format e mount
mkfs.ext4 -F /dev/md0
mkdir -p /mnt/blockchain
mount /dev/md0 /mnt/blockchain

# Auto-mount al boot
echo '/dev/md0 /mnt/blockchain ext4 defaults,nofail,discard 0 0' >> /etc/fstab

# Verifica
df -h
# Dovrebbe mostrare ~7.3 TB disponibili su /mnt/blockchain
```

### 3. Download e Build BSC Client

```bash
# Crea directory di lavoro
cd /mnt/blockchain
mkdir bsc && cd bsc

# Clone repository BSC ufficiale
git clone https://github.com/bnb-chain/bsc.git
cd bsc

# Build (richiede ~10 minuti)
make geth

# Verifica build
./build/bin/geth version
```

### 4. Download Snapshot (IMPORTANTE - evita 2 settimane di sync!)

```bash
# Vai alla directory data
cd /mnt/blockchain/bsc

# Download snapshot ufficiale BSC (6 TB, richiede 12-24 ore)
# Aggiorna URL da: https://github.com/bnb-chain/bsc-snapshots

# Verifica ultimo snapshot disponibile
curl -s https://snapshots.bnbchain.org/ | grep -o "geth.*tar.lz4" | head -1

# Download (esempio con snapshot Nov 2024)
wget -c https://snapshots.bnbchain.org/geth-20241115.tar.lz4

# Decomprimi (richiede 2-4 ore)
lz4 -d geth-20241115.tar.lz4 | tar xvf - -C ./

# Rinomina directory
mv server/data-seed/geth/chaindata ./geth-data
```

### 5. Configurazione BSC Node

```bash
# Crea config.toml
cat > /mnt/blockchain/bsc/config.toml << 'EOF'
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

# Trusted peers (bootnodes BSC ufficiali)
BootstrapNodes = [
  "enode://433297e67f95f56b8f8d81eeaf35e4b8f7b1d3b4f2a4e9f5c3a1b2c3d4e5f6a7@35.73.137.87:30311",
  "enode://1cc4534b14cfe351b2c8a8e5f3a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9@52.68.123.154:30311"
]
EOF
```

### 6. Script Avvio Node

```bash
# Crea script di avvio
cat > /mnt/blockchain/bsc/start_bsc.sh << 'EOF'
#!/bin/bash

# Directory
WORK_DIR="/mnt/blockchain/bsc"
cd $WORK_DIR

# Avvia in screen session
screen -dmS bsc-node bash -c "
  ./build/bin/geth \
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

echo "BSC node started in screen session 'bsc-node'"
echo "Attach with: screen -r bsc-node"
echo "Detach with: Ctrl+A then D"
echo "View logs: tail -f bsc-node.log"
EOF

chmod +x /mnt/blockchain/bsc/start_bsc.sh
```

### 7. Avvio Node

```bash
# Prima avvio
cd /mnt/blockchain/bsc
./start_bsc.sh

# Verifica che sia partito
screen -r bsc-node  # Ctrl+A D per uscire

# Controlla logs
tail -f /mnt/blockchain/bsc/bsc-node.log
```

### 8. Verifica Sync

```bash
# Installa web3
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt install -y nodejs
npm install -g web3

# Crea script verifica
cat > /tmp/check_sync.js << 'SCRIPT'
const Web3 = require('web3');
const web3 = new Web3('http://localhost:8545');

async function checkSync() {
    const syncStatus = await web3.eth.isSyncing();

    if (syncStatus) {
        console.log('⏳ Syncing...');
        console.log(`Current Block: ${syncStatus.currentBlock}`);
        console.log(`Highest Block: ${syncStatus.highestBlock}`);
        const percent = (syncStatus.currentBlock / syncStatus.highestBlock * 100).toFixed(2);
        console.log(`Progress: ${percent}%`);
    } else {
        const blockNum = await web3.eth.getBlockNumber();
        console.log('✅ Fully synced!');
        console.log(`Current Block: ${blockNum}`);
    }

    const peerCount = await web3.eth.net.getPeerCount();
    console.log(`Peers: ${peerCount}`);
}

checkSync().catch(console.error);
SCRIPT

node /tmp/check_sync.js
```

### 9. Ottimizzazione Performance

```bash
# Aumenta file descriptors
echo "fs.file-max = 1000000" >> /etc/sysctl.conf
echo "* soft nofile 1000000" >> /etc/security/limits.conf
echo "* hard nofile 1000000" >> /etc/security/limits.conf
sysctl -p

# Ottimizza network
cat >> /etc/sysctl.conf << EOF
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864
net.core.netdev_max_backlog = 5000
EOF
sysctl -p

# Restart node per applicare
screen -S bsc-node -X quit
./start_bsc.sh
```

### 10. Monitoring

```bash
# Installa htop e iotop
apt install -y htop iotop nethogs

# Monitor CPU/RAM
htop

# Monitor disk I/O
iotop

# Monitor network
nethogs

# Logs in real-time
tail -f /mnt/blockchain/bsc/bsc-node.log

# Check RPC
curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Timeline Prevista

```
Giorno 1:
- Ordine server: 1-24 ore per provisioning
- Setup OS: 1 ora
- Download snapshot: 12-24 ore

Giorno 2-3:
- Decompressione snapshot: 2-4 ore
- Configurazione node: 1 ora
- Sync rimanente: 6-12 ore

Giorno 3-4:
- Verifica funzionamento: 2-4 ore
- Test RPC calls: 1 ora
- Deploy tracker arbitraggio: 2-4 ore

TOTALE: 3-4 giorni per setup completo
```

## Costi Mensili

```
Server Hetzner AX52:        €53/mese
Backup storage (opzionale): €10/mese
-----------------------------------
TOTALE:                     €63/mese
```

## Testing RPC Speed

```bash
# Test latency a validator BSC Singapore
ping -c 10 54.179.23.240

# Output atteso da Germania:
# rtt min/avg/max = 180/200/250 ms

# Test RPC call speed
time curl -X POST http://localhost:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",false],"id":1}'

# Output atteso:
# real    0m0.050s  (50ms - MOLTO meglio di RPC pubblico!)
```

## Firewall (Sicurezza)

```bash
# Installa ufw
apt install -y ufw

# Consenti SSH
ufw allow 22/tcp

# Consenti solo RPC da tuo IP (IMPORTANTE!)
ufw allow from YOUR_HOME_IP to any port 8545 proto tcp
ufw allow from YOUR_HOME_IP to any port 8546 proto tcp

# Consenti P2P BSC
ufw allow 30311/tcp
ufw allow 30311/udp

# Abilita firewall
ufw enable
```

## Connessione dal Tuo PC

```bash
# Sul tuo PC, edita tracker per usare il nuovo RPC
# In scripts/cross_dex_arbitrage_tracker.py:

BSC_RPC = "http://YOUR_HETZNER_IP:8545"

# Test connessione
curl -X POST http://YOUR_HETZNER_IP:8545 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

## Prossimi Passi

1. Ordina server su Hetzner Server Auction
2. Segui setup passo-passo
3. Verifica RPC funzionante
4. Modifica tracker per usare nuovo RPC
5. Confronta performance: 18 min → 2-3 min per scan
6. Monitora opportunità trovate per 1 mese
7. Valuta se upgrade ulteriore è necessario
