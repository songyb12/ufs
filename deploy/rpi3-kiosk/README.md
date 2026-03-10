# UFS RPi3 Kiosk

Raspberry Pi 3에서 VIBE 대시보드를 TV에 풀스크린으로 표시하는 키오스크 모드.

## 요구사항
- Raspberry Pi 3 (Model B/B+)
- Raspberry Pi OS Lite (Bookworm, 64-bit 권장)
- HDMI 연결된 TV/모니터
- 홈 네트워크에서 UFS 서버 접근 가능

## 설치

```bash
# 1. RPi3에 파일 복사
scp -r deploy/rpi3-kiosk/ pi@rpi3-ip:~/ufs-kiosk/

# 2. kiosk.env 편집 — 서버 IP 설정
nano ~/ufs-kiosk/kiosk.env

# 3. 설치 스크립트 실행
cd ~/ufs-kiosk
sudo bash install.sh

# 4. 재부팅
sudo reboot
```

## 관리

| 명령어 | 설명 |
|--------|------|
| `sudo nano /opt/ufs-kiosk/kiosk.env` | URL/설정 변경 |
| `sudo systemctl restart lightdm` | 변경사항 적용 |
| `sudo systemctl stop lightdm` | 키오스크 중지 |
| `journalctl -u ufs-kiosk-watchdog` | 로그 확인 |

## 메모리 최적화 (RPi3 1GB)
- Chromium: renderer 1개 제한, GPU 비활성화
- GPU 메모리: 64MB (최소)
- 백그라운드 프로세스 비활성화
- 확장 프로그램 비활성화
