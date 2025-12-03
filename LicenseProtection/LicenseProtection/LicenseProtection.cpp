// LicenseProtection.cpp
// Deep Vision Gold License Protection DLL
// Copyright www.bigboy.kr

#include "pch.h"
#include <wininet.h>
#include <string>
#include <vector>

#pragma comment(lib, "wininet.lib")

#define MT5_EXPFUNC extern "C" __declspec(dllexport)

// ============ Protected Constants (No encryption for now) ============
namespace ProtectedConstants {
    const char ENCRYPTED_MAIN_API[] = "vps105.cafe24.com";
    const char ENCRYPTED_BACKUP1[] = "vps104.cafe24.com";
    const char ENCRYPTED_BACKUP2[] = "vps106.cafe24.com";
    const char ENCRYPTED_PATH[] = "/api/xau/";
    const char ENCRYPTED_PORT[] = "5005";

    const int API_TIMEOUT_VALUE = 5000;
    const int SERVER_CHECK_INTERVAL_VALUE = 250;
    const int VISUAL_TOP_MARGIN_VALUE = 40;
    const int LINE_HEIGHT_VALUE = 20;
    const int PANEL_HEIGHT_VALUE = 300;
    const int PANEL_MARGIN_VALUE = 10;
    const int SUMMARY_LINE_HEIGHT_VALUE = 20;
}

// No encryption for now - just return as is
std::string DecryptString(const char* str, int key = 1) {
    return std::string(str);
}

// URL Encoding
std::string UrlEncode(const std::string& str) {
    std::string result;
    char hex[4];

    for(size_t i = 0; i < str.length(); i++) {
        if(isalnum((unsigned char)str[i]) || str[i] == '-' || str[i] == '_' || str[i] == '.' || str[i] == '~') {
            result += str[i];
        }
        else if(str[i] == ' ') {
            result += '+';
        }
        else {
            sprintf_s(hex, 4, "%%%02X", (unsigned char)str[i]);
            result += hex;
        }
    }
    return result;
}

// ============ Constant Getters ============
MT5_EXPFUNC int GetApiTimeout() {
    return ProtectedConstants::API_TIMEOUT_VALUE;
}

MT5_EXPFUNC int GetServerCheckInterval() {
    return ProtectedConstants::SERVER_CHECK_INTERVAL_VALUE;
}

MT5_EXPFUNC int GetVisualTopMargin() {
    return ProtectedConstants::VISUAL_TOP_MARGIN_VALUE;
}

MT5_EXPFUNC int GetLineHeight() {
    return ProtectedConstants::LINE_HEIGHT_VALUE;
}

MT5_EXPFUNC int GetPanelHeight() {
    return ProtectedConstants::PANEL_HEIGHT_VALUE;
}

MT5_EXPFUNC int GetPanelMargin() {
    return ProtectedConstants::PANEL_MARGIN_VALUE;
}

MT5_EXPFUNC int GetSummaryLineHeight() {
    return ProtectedConstants::SUMMARY_LINE_HEIGHT_VALUE;
}

MT5_EXPFUNC void GetMainApiUrl(wchar_t* buffer, int bufferSize) {
    std::string decrypted = DecryptString(ProtectedConstants::ENCRYPTED_MAIN_API);
    MultiByteToWideChar(CP_UTF8, 0, decrypted.c_str(), -1, buffer, bufferSize);
}

MT5_EXPFUNC void GetBackupApiUrl1(wchar_t* buffer, int bufferSize) {
    std::string decrypted = DecryptString(ProtectedConstants::ENCRYPTED_BACKUP1);
    MultiByteToWideChar(CP_UTF8, 0, decrypted.c_str(), -1, buffer, bufferSize);
}

MT5_EXPFUNC void GetBackupApiUrl2(wchar_t* buffer, int bufferSize) {
    std::string decrypted = DecryptString(ProtectedConstants::ENCRYPTED_BACKUP2);
    MultiByteToWideChar(CP_UTF8, 0, decrypted.c_str(), -1, buffer, bufferSize);
}

MT5_EXPFUNC void GetApiPath(wchar_t* buffer, int bufferSize) {
    std::string decrypted = DecryptString(ProtectedConstants::ENCRYPTED_PATH);
    MultiByteToWideChar(CP_UTF8, 0, decrypted.c_str(), -1, buffer, bufferSize);
}

MT5_EXPFUNC void GetPortNo(wchar_t* buffer, int bufferSize) {
    std::string decrypted = DecryptString(ProtectedConstants::ENCRYPTED_PORT);
    MultiByteToWideChar(CP_UTF8, 0, decrypted.c_str(), -1, buffer, bufferSize);
}

// ============ License Check Function ============
MT5_EXPFUNC int CheckLicenseOnline(
    long accountNumber,
    const wchar_t* serverName,
    const wchar_t* symbol,
    const wchar_t* nickname,
    double balance,
    double equity,
    double profit,
    wchar_t* errorMessage,
    int errorMessageSize,
    wchar_t* successServer,
    int successServerSize
) {
    std::string servers[] = {
        DecryptString(ProtectedConstants::ENCRYPTED_MAIN_API),
        DecryptString(ProtectedConstants::ENCRYPTED_BACKUP1),
        DecryptString(ProtectedConstants::ENCRYPTED_BACKUP2)
    };

    std::string apiPath = DecryptString(ProtectedConstants::ENCRYPTED_PATH);
    std::string port = DecryptString(ProtectedConstants::ENCRYPTED_PORT);

    for(int i = 0; i < 3; i++) {
        char szServerName[256], szSymbol[32], szNickname[64];
        WideCharToMultiByte(CP_UTF8, 0, serverName, -1, szServerName, 256, NULL, NULL);
        WideCharToMultiByte(CP_UTF8, 0, symbol, -1, szSymbol, 32, NULL, NULL);
        WideCharToMultiByte(CP_UTF8, 0, nickname, -1, szNickname, 64, NULL, NULL);

        std::string encodedServer = UrlEncode(szServerName);
        std::string encodedSymbol = UrlEncode(szSymbol);
        std::string encodedNickname = UrlEncode(szNickname);

        char url[2048];
        sprintf_s(url, 2048,
            "http://%s:%s%s?balance=%.2f&equity=%.2f&profit=%.2f&server=%s&account=%lld&symbol=%s&nickname=%s&licensecheck=yes",
            servers[i].c_str(),
            port.c_str(),
            apiPath.c_str(),
            balance,
            equity,
            profit,
            encodedServer.c_str(),
            (long long)accountNumber,
            encodedSymbol.c_str(),
            encodedNickname.c_str()
        );

        HINTERNET hInternet = InternetOpenA("MT5-License-Checker/1.0",
            INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);

        if(!hInternet) continue;

        HINTERNET hConnect = InternetOpenUrlA(hInternet, url, NULL, 0,
            INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE | INTERNET_FLAG_PRAGMA_NOCACHE, 0);

        if(!hConnect) {
            InternetCloseHandle(hInternet);
            continue;
        }

        char buffer[8192] = {0};
        DWORD bytesRead = 0;
        DWORD totalBytesRead = 0;

        while(InternetReadFile(hConnect, buffer + totalBytesRead,
              sizeof(buffer) - totalBytesRead - 1, &bytesRead) && bytesRead > 0) {
            totalBytesRead += bytesRead;
            if(totalBytesRead >= sizeof(buffer) - 1) break;
        }

        InternetCloseHandle(hConnect);
        InternetCloseHandle(hInternet);

        if(totalBytesRead == 0) continue;

        buffer[totalBytesRead] = 0;
        std::string response(buffer);

        if(response.find("\"next_candle_trend\":\"OK\"") != std::string::npos ||
           response.find("\"next_candle_trend\": \"OK\"") != std::string::npos) {
            MultiByteToWideChar(CP_UTF8, 0, servers[i].c_str(), -1,
                successServer, successServerSize);
            return 1;
        }

        if(response.find("\"next_candle_trend\":\"update\"") != std::string::npos ||
           response.find("\"next_candle_trend\": \"update\"") != std::string::npos) {
            MultiByteToWideChar(CP_UTF8, 0, servers[i].c_str(), -1,
                successServer, successServerSize);
            return 2;
        }

        if(response.find("\"next_candle_trend\":\"NOOK\"") != std::string::npos ||
           response.find("\"next_candle_trend\": \"NOOK\"") != std::string::npos) {
            size_t pos = response.find("\"key_factors\":");
            if(pos != std::string::npos) {
                pos = response.find("\"", pos + 14);
                if(pos != std::string::npos) {
                    pos++;
                    size_t endPos = response.find("\"", pos);
                    if(endPos != std::string::npos) {
                        std::string msg = response.substr(pos, endPos - pos);
                        MultiByteToWideChar(CP_UTF8, 0, msg.c_str(), -1,
                            errorMessage, errorMessageSize);
                    }
                }
            }

            if(wcslen(errorMessage) == 0) {
                wcscpy_s(errorMessage, errorMessageSize, L"License verification failed");
            }
            return 0;
        }
    }

    wcscpy_s(errorMessage, errorMessageSize, L"All servers failed");
    return -1;
}

MT5_EXPFUNC bool CheckAccountLicense(long currentAccount, long authorizedAccount) {
    return (currentAccount == authorizedAccount);
}

MT5_EXPFUNC bool CheckDateLicense(long currentTimestamp, long expiryTimestamp) {
    return (currentTimestamp <= expiryTimestamp);
}

MT5_EXPFUNC void GetDllVersion(wchar_t* buffer, int bufferSize) {
    wcscpy_s(buffer, bufferSize, L"1.0.0");
}
