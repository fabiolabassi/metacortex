#!/usr/bin/env bash
# VMs de teste do roster-audit em QEMU/KVM, rede de usuario (sem root, sem
# libvirt). O SSH de cada VM fica em 127.0.0.1:<porta>.
#
#   bash vm.sh chaves                     gera as chaves de teste (fora do repo)
#   bash vm.sh criar conforme             Ubuntu 24.04 dentro do baseline  (porta 2221)
#   bash vm.sh criar desvios              Ubuntu 22.04 fora do baseline    (porta 2222)
#   bash vm.sh parar <nome>
#   bash vm.sh estado
set -euo pipefail
AQUI=$(cd "$(dirname "$0")" && pwd)
CACHE=${CACHE:-$HOME/.cache/metacortex-vms}
CHAVES=$CACHE/keys
declare -A IMAGEM=([conforme]=ubuntu-24.04-server-cloudimg-amd64.img [desvios]=ubuntu-22.04-server-cloudimg-amd64.img)
declare -A PORTA=([conforme]=2221 [desvios]=2222)

chaves() {
  mkdir -p "$CHAVES" && chmod 700 "$CHAVES"
  [ -f "$CHAVES/auditor" ] || ssh-keygen -q -t ed25519 -N '' -C 'platform@metacortex-platform' -f "$CHAVES/auditor"
  [ -f "$CHAVES/dozer" ]   || ssh-keygen -q -t ed25519 -N '' -C 'dozer@notebook' -f "$CHAVES/dozer"
  echo "chaves em $CHAVES"
}

criar() {
  local nome=$1 dir=$CACHE/$1
  chaves >/dev/null
  mkdir -p "$dir"
  qemu-img create -q -f qcow2 -F qcow2 -b "$CACHE/${IMAGEM[$nome]}" "$dir/disco.qcow2" 8G
  sed -e "s|@CHAVE_PLATAFORMA@|$(cat "$CHAVES/auditor.pub")|" \
      -e "s|@CHAVE_ESTRANHA@|$(cat "$CHAVES/dozer.pub")|" \
      "$AQUI/cloud-init/$nome.yaml" > "$dir/user-data"
  printf 'instance-id: %s\nlocal-hostname: construct-node-%s\n' "$nome" \
    "$([ "$nome" = conforme ] && echo 01 || echo 02)" > "$dir/meta-data"
  genisoimage -quiet -output "$dir/seed.iso" -volid cidata -joliet -rock "$dir/user-data" "$dir/meta-data"
  qemu-system-x86_64 -enable-kvm -cpu host -m 768 -smp 1 -name "roster-$nome" \
    -drive file="$dir/disco.qcow2",if=virtio -drive file="$dir/seed.iso",media=cdrom \
    -netdev user,id=n0,hostfwd=tcp:127.0.0.1:${PORTA[$nome]}-:22 -device virtio-net-pci,netdev=n0 \
    -display none -serial file:"$dir/console.log" -daemonize -pidfile "$dir/pid"
  echo "VM $nome subindo; SSH em 127.0.0.1:${PORTA[$nome]} (cloud-init leva alguns minutos)"
}

parar() { local p=$CACHE/$1/pid; [ -f "$p" ] && kill "$(cat "$p")" 2>/dev/null; rm -rf "${CACHE:?}/$1"; echo "VM $1 removida"; }
estado() { for n in conforme desvios; do printf '%-9s ' $n; [ -f "$CACHE/$n/pid" ] && kill -0 "$(cat "$CACHE/$n/pid")" 2>/dev/null && echo "rodando (127.0.0.1:${PORTA[$n]})" || echo parada; done; }

case "${1:-}" in
  chaves) chaves ;; criar) criar "$2" ;; parar) parar "$2" ;; estado) estado ;;
  *) sed -n '2,10p' "$0"; exit 2 ;;
esac
