#pragma once

#include <filesystem>
#include <fstream>
#include <string>
#include <cstdio>

// GeneralsX @feature Codex 26/10/2026 Consume an explicit Files-app request before DXVK starts.
namespace gxcache {
namespace fs = std::filesystem;
struct Result { bool requested = false, completed = false; unsigned removed = 0, errors = 0; };
inline bool testDirectory(const fs::path& path) {
 const std::string name = path.filename().string(), prefix = "dxvk-test-";
 if (name.size() <= prefix.size() || name.compare(0, prefix.size(), prefix) != 0) return false;
 for (size_t i = prefix.size(); i < name.size(); ++i) {
  const char c = name[i];
  if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_' || c == '-')) return false;
 }
 return true;
}
inline void clearFiles(const fs::path& directory, Result& result, bool includeTests) {
 std::error_code ec;
 const auto status = fs::symlink_status(directory, ec);
 if (ec == std::errc::no_such_file_or_directory) return;
 if (ec || !fs::is_directory(status) || fs::is_symlink(status)) { ++result.errors; return; }
 fs::directory_iterator it(directory, ec), end;
 if (ec) { ++result.errors; return; }
 while (it != end) {
  const fs::path path = it->path();
  const auto entry = it->symlink_status(ec);
  if (ec) { ++result.errors; ec.clear(); }
  else if (!fs::is_symlink(entry)) {
   if (fs::is_regular_file(entry) && path.extension() == ".dxvk-cache") {
    if (fs::remove(path, ec)) ++result.removed;
    if (ec) { ++result.errors; ec.clear(); }
   } else if (includeTests && fs::is_directory(entry) && testDirectory(path)) {
    clearFiles(path, result, false);
   }
  }
  it.increment(ec);
  if (ec) { ++result.errors; break; }
 }
}
inline Result clearRequested(const fs::path& home, const fs::path& activeCache) {
 Result result;
 const auto documents = home / "Documents";
 const auto request = documents / "Clear DXVK Cache";
 const auto root = home / "Library" / "Caches";
 std::error_code ec;
 const auto status = fs::symlink_status(request, ec);
 if (ec || !fs::exists(status)) return result;
 result.requested = true;
 // Only an empty directory or regular request file is consumed. Never follow a request symlink.
 bool valid = !fs::is_symlink(status) && (fs::is_directory(status) || fs::is_regular_file(status));
 if (valid && fs::is_directory(status)) { valid = fs::is_empty(request, ec); if (ec) valid = false; }
 if (!valid) ++result.errors;
 else {
  // Do not claim success for an externally overridden cache path we deliberately leave untouched.
  if (activeCache != root && !(activeCache.parent_path() == root && testDirectory(activeCache))) ++result.errors;
  clearFiles(root, result, true);
  if (!result.errors) {
   if (!fs::remove(request, ec) || ec) ++result.errors;
  }
 }
 result.completed = !result.errors;
 const auto report = documents / "DXVK Cache Reset Result.txt";
 ec.clear();
 const auto reportStatus = fs::symlink_status(report, ec);
 if ((!ec && fs::is_regular_file(reportStatus)) || ec == std::errc::no_such_file_or_directory || (!ec && !fs::exists(reportStatus))) {
  std::ofstream out(report);
  if (out) {
   out << (result.completed ? "DXVK cache cleared.\n" : "DXVK cache reset incomplete; the request was kept.\n")
       << "Cache files removed: " << result.removed << "\nErrors: " << result.errors << "\n"
       << "Game data, saves, settings and other caches were not selected.\n"
       << "The next run may compile pipelines again.\n";
  }
 }
 std::fprintf(stderr, "[DXVK_CACHE_RESET] status=%s removed=%u errors=%u\n",
  result.completed ? "cleared" : "incomplete", result.removed, result.errors);
 return result;
}
}
