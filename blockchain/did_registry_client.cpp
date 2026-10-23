// Minimal Ethereum JSON-RPC client for genuine blockchain-anchored
// DID/VC storage and retrieval (Eq. 16-17, Algorithm 1 step 6).
// Function selectors below are fixed constants computed once via
// `solc --hashes` on DIDRegistry.sol -- no runtime Keccak-256 needed.
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <chrono>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <string>
#include <vector>
#include <stdexcept>
#include <thread>

using json = nlohmann::json;

// Fixed selectors from solc --hashes (see build note at bottom)
static const std::string SEL_STORE_DOCUMENT       = "2fc29e49"; // storeDocument(bytes32,bytes)
static const std::string SEL_RETRIEVE_DOCUMENT    = "06f3c1b9"; // retrieveDocument(bytes32)
static const std::string SEL_ANCHOR_CREDENTIAL    = "b534d652"; // anchorCredential(bytes32,bytes)
static const std::string SEL_RETRIEVE_CREDENTIAL  = "0103209d"; // retrieveCredential(bytes32)

std::string bytesToHex(const unsigned char *data, size_t len) {
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    for (size_t i = 0; i < len; ++i) oss << std::setw(2) << (int)data[i];
    return oss.str();
}

std::string bytesToHex(const std::vector<unsigned char> &data) {
    return bytesToHex(data.data(), data.size());
}

std::vector<unsigned char> hexToBytes(const std::string &hex) {
    std::string h = hex;
    if (h.rfind("0x", 0) == 0) h = h.substr(2);
    std::vector<unsigned char> out;
    for (size_t i = 0; i + 1 < h.size(); i += 2) {
        out.push_back(static_cast<unsigned char>(std::stoi(h.substr(i, 2), nullptr, 16)));
    }
    return out;
}

// Pad a hex string (no 0x) to 32 bytes (64 hex chars), left-padding with zeros
std::string padTo32(const std::string &hex) {
    std::string h = hex;
    while (h.size() < 64) h = "0" + h;
    return h;
}

// Right-pad data to a multiple of 32 bytes (Ethereum ABI convention for bytes)
std::string rightPadTo32Multiple(const std::string &hex) {
    std::string h = hex;
    while (h.size() % 64 != 0) h += "0";
    return h;
}

// ABI-encode a call to fn(bytes32 key, bytes data)
std::string encodeStoreCall(const std::string &selector, const std::string &keyHex32,
                             const std::vector<unsigned char> &data) {
    std::ostringstream call;
    call << selector;
    call << padTo32(keyHex32);                 // bytes32 key
    call << padTo32("40");                      // offset to dynamic bytes = 0x40
    std::ostringstream lenHex;
    lenHex << std::hex << data.size();
    call << padTo32(lenHex.str());               // length of bytes
    call << rightPadTo32Multiple(bytesToHex(data)); // the bytes themselves, right-padded
    return call.str();
}

// ABI-encode a call to fn(bytes32 key)
std::string encodeRetrieveCall(const std::string &selector, const std::string &keyHex32) {
    return selector + padTo32(keyHex32);
}

// Decode a dynamic `bytes` ABI return value into raw bytes
std::vector<unsigned char> decodeBytesReturn(const std::string &resultHex) {
    std::string h = resultHex;
    if (h.rfind("0x", 0) == 0) h = h.substr(2);
    if (h.size() < 128) return {}; // empty / not found
    // First 32 bytes: offset (always 0x20 for a single dynamic return). Next 32: length.
    std::string lenHex = h.substr(64, 64);
    size_t len = std::stoul(lenHex, nullptr, 16);
    if (len == 0) return {};
    std::string dataHex = h.substr(128, len * 2);
    return hexToBytes(dataHex);
}

static size_t CurlWriteCallback(void *contents, size_t size, size_t nmemb, void *userp) {
    ((std::string *)userp)->append((char *)contents, size * nmemb);
    return size * nmemb;
}

json RpcCall(const std::string &rpcUrl, const std::string &method, const json &params) {
    CURL *curl = curl_easy_init();
    if (!curl) throw std::runtime_error("curl init failed");

    json body = {{"jsonrpc", "2.0"}, {"method", method}, {"params", params}, {"id", 1}};
    std::string bodyStr = body.dump();
    std::string response;

    struct curl_slist *headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, rpcUrl.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, bodyStr.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, CurlWriteCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, (long)bodyStr.size());
    if (getenv("RPC_DEBUG")) curl_easy_setopt(curl, CURLOPT_VERBOSE, 1L);

    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK) {
        throw std::runtime_error(std::string("curl error: ") + curl_easy_strerror(res));
    }

    json j = json::parse(response);
    if (j.contains("error")) {
        throw std::runtime_error("RPC error: " + j["error"].dump());
    }
    return j["result"];
}

class DIDRegistryClient {
public:
    DIDRegistryClient(std::string rpcUrl, std::string fromAccount, std::string contractAddress)
        : rpcUrl_(std::move(rpcUrl)), from_(std::move(fromAccount)), contract_(std::move(contractAddress)) {}

    // Genuine network write: send tx, wait for receipt. Returns elapsed ms.
    double SendStore(const std::string &selector, const std::string &keyHex32,
                      const std::vector<unsigned char> &data) {
        auto start = std::chrono::high_resolution_clock::now();

        std::string callData = "0x" + encodeStoreCall(selector, keyHex32, data);
        json txParams = {{"from", from_}, {"to", contract_}, {"data", callData}, {"gas", "0x100000"}};
        json txHash = RpcCall(rpcUrl_, "eth_sendTransaction", json::array({txParams}));

        // Ganache instamines by default; poll briefly for the receipt.
        json receipt = nullptr;
        for (int attempt = 0; attempt < 50; ++attempt) {
            receipt = RpcCall(rpcUrl_, "eth_getTransactionReceipt", json::array({txHash.get<std::string>()}));
            if (!receipt.is_null()) break;
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        if (receipt.is_null()) throw std::runtime_error("transaction receipt not found");

        auto end = std::chrono::high_resolution_clock::now();
        return std::chrono::duration<double, std::milli>(end - start).count();
    }

    // Genuine network read (eth_call). Returns elapsed ms; result via out param.
    double Retrieve(const std::string &selector, const std::string &keyHex32,
                     std::vector<unsigned char> &out) {
        auto start = std::chrono::high_resolution_clock::now();

        std::string callData = "0x" + encodeRetrieveCall(selector, keyHex32);
        json callParams = {{"to", contract_}, {"data", callData}};
        json fullParams = json::array({callParams, "latest"});
        json result = RpcCall(rpcUrl_, "eth_call", fullParams);
        out = decodeBytesReturn(result.get<std::string>());

        auto end = std::chrono::high_resolution_clock::now();
        return std::chrono::duration<double, std::milli>(end - start).count();
    }

private:
    std::string rpcUrl_, from_, contract_;
};

int main(int argc, char **argv) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <fromAccount> <contractAddress> [rpcPort]\n";
        return 1;
    }
    std::string fromAccount = argv[1];
    std::string contractAddress = argv[2];
    std::string rpcPort = (argc >= 4) ? argv[3] : "7545";
    std::string rpcUrl = "http://127.0.0.1:" + rpcPort;
    std::cout << "Connecting to " << rpcUrl << "\n";

    curl_global_init(CURL_GLOBAL_DEFAULT);
    DIDRegistryClient client(rpcUrl, fromAccount, contractAddress);

    // Simulate storing a DID document: key = a fake 32-byte "Gamma" hash,
    // value = a fake signed document blob.
    std::string didKeyHex = "aa11bb22cc33dd44ee55ff66aa77bb88cc99dd00ee11ff22aa33bb44cc55dd66";
    std::vector<unsigned char> docData = {'D','I','D','-','D','O','C','-','v','1',
                                           0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};

    std::cout << "=== Genuine blockchain-anchored DID store/retrieve ===\n";
    double storeMs = client.SendStore(SEL_STORE_DOCUMENT, didKeyHex, docData);
    std::cout << "Store (write tx + receipt wait): " << storeMs << " ms\n";

    std::vector<unsigned char> retrieved;
    double retrieveMs = client.Retrieve(SEL_RETRIEVE_DOCUMENT, didKeyHex, retrieved);
    std::cout << "Retrieve (eth_call):              " << retrieveMs << " ms\n";

    bool matches = (retrieved == docData);
    std::cout << "Round-trip data matches original: " << (matches ? "YES (correct)" : "NO (BUG)") << "\n";
    std::cout << "Retrieved " << retrieved.size() << " bytes: ";
    for (auto b : retrieved) std::cout << std::hex << (int)b << " ";
    std::cout << std::dec << "\n\n";

    // Run several iterations to get a feel for variance
    std::cout << "=== 10 repeated store+retrieve cycles ===\n";
    for (int i = 0; i < 10; ++i) {
        std::string key = didKeyHex.substr(0, 62) + (i < 10 ? "0" + std::to_string(i) : std::to_string(i));
        std::vector<unsigned char> data = docData;
        data.push_back(static_cast<unsigned char>(i));
        double s = client.SendStore(SEL_STORE_DOCUMENT, key, data);
        std::vector<unsigned char> r;
        double v = client.Retrieve(SEL_RETRIEVE_DOCUMENT, key, r);
        bool ok = (r == data);
        std::cout << "  iter " << i << ": store=" << s << "ms retrieve=" << v << "ms match=" << (ok ? "yes" : "NO") << "\n";
    }

    curl_global_cleanup();
    return 0;
}