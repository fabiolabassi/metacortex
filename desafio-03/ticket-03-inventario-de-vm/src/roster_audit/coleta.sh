# Coleta do roster-audit. Enviado por stdin para `/bin/sh -s` no host auditado.
# So LEITURA: nenhum comando aqui cria, altera ou apaga arquivo no host.
# Cada secao sai como "##RA## <nome> rc=<codigo>" seguida do stdout do comando;
# stderr e descartado no host (o rc diz se o dado foi lido).
# A primeira linha do stdin define RA_SUDO=0|1 (vem do --sudo); nada mais do
# usuario e interpolado neste script.
export LC_ALL=C
secao() { nome=$1; shift; saida=$("$@" 2>/dev/null); rc=$?; printf '##RA## %s rc=%s\n%s\n' "$nome" "$rc" "$saida"; }
privilegiado() { if [ "$RA_SUDO" = 1 ]; then sudo -n "$@"; else "$@"; fi; }
portas_em_escuta() {
  # Com --sudo, o ss -p enxerga o processo dono de qualquer porta. Se o sudo
  # falhar, cai para o ss comum: as portas continuam verificaveis, so sem processo.
  if [ "$RA_SUDO" = 1 ] && sudo -n ss -H -t -l -n -p; then return 0; fi
  ss -H -t -l -n -p
}
chaves_de_todas_as_contas() {
  # So com sudo: le o authorized_keys de root e de cada /home/*, prefixando a conta.
  [ "$RA_SUDO" = 1 ] || return 99
  sudo -n sh -c 'for f in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys; do
      [ -r "$f" ] || continue
      conta=$(echo "$f" | cut -d/ -f2-3 | sed "s|^root/.ssh|root|; s|^home/||")
      sed "s|^|$conta |" "$f"
    done; true'
}

secao hostname hostname
secao os_release cat /etc/os-release
secao kernel uname -r
secao units systemctl list-units --type=service,socket --state=active --no-legend --plain --no-pager
secao swaps cat /proc/swaps
secao listen portas_em_escuta
secao authkeys_self sh -c 'f="$HOME/.ssh/authorized_keys"; [ -e "$f" ] || exit 0; cat "$f"'
secao authkeys_all chaves_de_todas_as_contas
secao sshd_t privilegiado sshd -T
secao timedatectl timedatectl show -p NTPSynchronized -p NTP
secao whoami id -un
