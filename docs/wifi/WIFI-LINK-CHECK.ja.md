# C号機 STA 基本検証ツール

`scripts/wifi-link-check.py`は、既存接続を確認するread-only試験を既定にする。
SSID、BSSID、MAC、アドレス、DNS応答値、PSKは出力しない。

```sh
scripts/wifi-link-check.py \
  --iface <実測したSTA_IF> --band 2.4 \
  --management-if <実測した有線管理IF> \
  --gateway <STA subnet gateway> --dns-server <per-link DNS> \
  --domain example.com --security wpa2
```

5GHzでは`--band 5`を指定する。`ip route get`でgatewayとDNS resolverの経路が指定Wi-Fi IFを使うこと、default routeが有線管理IFだけを使うことを確認してから疎通を試し、後のdefault routeが同一であることも確認する。経路が期待と違う場合はrouteを変更せず失敗する。

一時切断・再接続は通常試験に含めない。ユーザーが実測を許可した作業内で、かつ管理経路が有線に限定されている場合だけ`--exercise-reconnect`を追加する。このオプションは稼働中のwpa_supplicant制御socketから一時的なdisconnect/reconnectを指示し、設定ファイルやrouteを変更しない。復帰しない場合は再connectを再要求して失敗を返す。

WPA3 STAの既存プロファイルを試す場合は`--security sae`を指定する。これは現行交渉結果が`SAE`であることを確認するもので、新規のWPA3設定作成やAP変更はしない。

速度測定は所有者管理のiperf3 peerがあるときだけ、`--throughput-server <peer>`を加える。測定先のrouteがWi-Fi IFでなければ停止する。結果は10秒TCP試験の受信Mbpsである。iperf3 peerがない場合は未測定とする。

このツールは、再起動後の自動復帰、APの外部Beacon、クライアントassociation、DHCP、WPA3 AP受入を単独では検証しない。それらは別途記録が必要である。
