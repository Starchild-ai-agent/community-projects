/*
 * ============================================================
 *  方案A：向心力定量演示仪 - ESP32 固件
 *  功能：读取 HX711 力传感器 + 红外光电门测周期
 *        通过 USB 串口 + 蓝牙BLE 双通道发送数据
 *  硬件：ESP32-WROOM-32 + HX711(20kg) + S型传感器 + 红外光电门
 *  引脚：
 *    HX711 DOUT -> GPIO33   HX711 SCK -> GPIO32
 *    光电门 DOUT-> GPIO27（外部中断，下降沿触发）
 *  数据格式（串口 & 蓝牙统一，JSON行）：
 *    {"t":12345.6,"force":1.23,"omega":5.67,"period":1.11,"rpm":54,"state":"RUN"}
 *    state: IDLE(待机) | RUN(采集中) | ZERO(归零中)
 *  串口波特率 115200，网页端用 Web Serial API 读取
 * ============================================================
 */

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE290x.h>

// ---------- 引脚定义 ----------
#define HX711_DOUT   33
#define HX711_SCK    32
#define PHOTO_PIN    27

// ---------- HX711 参数 ----------
#define HX711_GAIN   128     // A通道128倍增益
#define SCALE_FACTOR -22000.0  // 标定系数：raw / SCALE = 力(N)，需现场标定
#define ZERO_RAW_INIT 8388608  // 上电默认零点（中点），标定后更新

// ---------- 全局变量 ----------
long   zeroRaw = ZERO_RAW_INIT;     // 零点原始值
double scale = SCALE_FACTOR;        // 标定系数
volatile unsigned long lastEdgeUs = 0;
volatile unsigned long periodUs = 0;     // 周期（微秒）
volatile int  edgeCount = 0;
double forceN = 0.0;
double omega = 0.0;
double periodS = 0.0;
int    rpm = 0;
String stateStr = "IDLE";
bool   running = false;

// 蓝牙
BLEServer* pServer = nullptr;
BLECharacteristic* pChar = nullptr;
bool bleConnected = false;

// ---------- HX711 读取（直接GPIO，不依赖库） ----------
long readHX711() {
  // 等待DOUT变低（数据就绪）
  long timeout = millis();
  while (digitalRead(HX711_DOUT) == HIGH) {
    if (millis() - timeout > 200) return 0; // 超时
  }
  // 读24位
  long value = 0;
  for (int i = 0; i < 24; i++) {
    digitalWrite(HX711_SCK, HIGH);
    delayMicroseconds(2);
    value = (value << 1) | digitalRead(HX711_DOUT);
    digitalWrite(HX711_SCK, LOW);
    delayMicroseconds(2);
  }
  // 设置通道A增益128：发送1个时钟脉冲
  digitalWrite(HX711_SCK, HIGH);
  delayMicroseconds(2);
  digitalWrite(HX711_SCK, LOW);
  delayMicroseconds(2);
  // 转有符号
  if (value & 0x800000) value |= 0xFF000000;
  return value;
}

double readForce() {
  long raw = readHX711();
  if (raw == 0) return forceN; // 超时则保持
  return (double)(raw - zeroRaw) / scale;
}

// ---------- 光电门中断 ----------
void IRAM_ATTR photoISR() {
  unsigned long now = micros();
  if (lastEdgeUs != 0) {
    periodUs = now - lastEdgeUs;
  }
  lastEdgeUs = now;
  edgeCount++;
}

// ---------- 蓝牙回调 ----------
class MyServerCallbacks: public BLEServerCallbacks {
  void onConnect(BLEServer* p) { bleConnected = true; }
  void onDisconnect(BLEServer* p) { bleConnected = false; p->startAdvertising(); }
};

void initBLE() {
  BLEDevice::init("CentrifugalForce");
  BLEDevice::setMTU(185);
  pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  BLEService *pService = pServer->createService(
    BLEUUID("0000FFE0-0000-1000-8000-00805F9B34FB"));
  pChar = pService->createCharacteristic(
    BLEUUID("0000FFE1-0000-1000-8000-00805F9B34FB"),
    BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_WRITE
  );
  pChar->addDescriptor(new BLE2902());
  pService->start();
  BLEAdvertising *pAdv = BLEDevice::getAdvertising();
  pAdv->addServiceUUID("0000FFE0-0000-1000-8000-00805F9B34FB");
  pAdv->start();
}

// ---------- 串口命令处理 ----------
void handleCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();
  if (cmd == "START") {
    running = true; stateStr = "RUN";
  } else if (cmd == "STOP") {
    running = false; stateStr = "IDLE";
  } else if (cmd == "ZERO") {
    stateStr = "ZERO";
    long sum = 0; int n = 20;
    for (int i = 0; i < n; i++) { sum += readHX711(); delay(10); }
    zeroRaw = sum / n;
    stateStr = "IDLE";
  } else if (cmd.startsWith("SCALE:")) {
    scale = cmd.substring(6).toDouble();
  } else if (cmd == "INFO") {
    Serial.printf("{\"info\":\"zero=%ld scale=%.1f edge=%d\"}\n", zeroRaw, scale, edgeCount);
  }
}

// ---------- setup ----------
void setup() {
  Serial.begin(115200);
  pinMode(HX711_SCK, OUTPUT);
  pinMode(HX711_DOUT, INPUT);
  pinMode(PHOTO_PIN, INPUT_PULLUP);
  digitalWrite(HX711_SCK, LOW);
  // 光电门下降沿中断
  attachInterrupt(digitalPinToInterrupt(PHOTO_PIN), photoISR, FALLING);
  // 初始化蓝牙
  initBLE();
  Serial.println("{\"info\":\"ESP32 向心力演示仪 已启动 v1.0\"}");
  Serial.println("{\"info\":\"命令：START / STOP / ZERO / SCALE:数值 / INFO\"}");
}

// ---------- loop ----------
unsigned long lastSend = 0;
unsigned long lastPeriodUpdate = 0;
void loop() {
  // 读串口命令
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    handleCommand(cmd);
  }
  // 蓝牙命令
  if (pChar && pChar->getValue().length() > 0) {
    handleCommand(pChar->getValue().c_str());
    pChar->setValue("");
  }

  // 读力
  forceN = readForce();

  // 计算角速度（用最近周期，2秒内有效，否则判停转）
  unsigned long now = micros();
  if (periodUs > 0 && (now - lastEdgeUs) < 2000000) {
    periodS = periodUs / 1000000.0;
    omega = 2.0 * PI / periodS;
    rpm = (int)(60.0 / periodS);
  } else {
    omega = 0; rpm = 0; periodS = 0;
  }

  // 每100ms发送一次
  if (millis() - lastSend > 100) {
    char buf[160];
    snprintf(buf, sizeof(buf),
      "{\"t\":%.2f,\"force\":%.3f,\"omega\":%.3f,\"period\":%.4f,\"rpm\":%d,\"state\":\"%s\"}\n",
      millis() / 1000.0, forceN, omega, periodS, rpm, stateStr.c_str());
    Serial.print(buf);
    if (bleConnected && pChar) {
      pChar->setValue(String(buf));
      pChar->notify();
    }
    lastSend = millis();
  }
  delay(5);
}
