import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';

void main() => runApp(const GoreeCloudMonitorApp());

class ServiceStatus {
  const ServiceStatus(this.name, this.state, this.latency);
  final String name;
  final String state;
  final int? latency;
  factory ServiceStatus.fromJson(Map<String, dynamic> value) => ServiceStatus(
        value['name'] as String? ?? 'Unnamed',
        value['state'] as String? ?? 'pending',
        (value['last_latency_ms'] as num?)?.toInt(),
      );
}

class Snapshot {
  const Snapshot(this.services, this.incidents);
  final List<ServiceStatus> services;
  final List<String> incidents;
  factory Snapshot.fromJson(Map<String, dynamic> value) => Snapshot(
        ((value['monitors'] as List<dynamic>?) ?? [])
            .map((m) => ServiceStatus.fromJson(m as Map<String, dynamic>))
            .toList(),
        ((value['incidents'] as List<dynamic>?) ?? [])
            .map((i) =>
                (i as Map<String, dynamic>)['monitor_name'] as String? ??
                'Service')
            .toList(),
      );
}

class StatusClient {
  Future<Snapshot> read(String address) async {
    final uri = Uri.tryParse(address.trim());
    if (uri == null ||
        !uri.hasAuthority ||
        !(uri.scheme == 'https' ||
            (uri.scheme == 'http' &&
                (uri.host == '127.0.0.1' || uri.host == 'localhost'))) ||
        uri.userInfo.isNotEmpty ||
        uri.fragment.isNotEmpty) {
      throw const FormatException(
          'Use an HTTPS server address without credentials.');
    }
    final target = uri.replace(
      path: '${uri.path.replaceAll(RegExp(r'/$'), '')}/api/v1/status',
      query: '',
    );
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final req =
          await client.getUrl(target).timeout(const Duration(seconds: 8));
      req.headers.set('Accept', 'application/json');
      final res = await req.close().timeout(const Duration(seconds: 8));
      if (res.statusCode != 200) {
        throw HttpException('HTTP ${res.statusCode}');
      }
      final text = await res.transform(utf8.decoder).join();
      if (text.length > 1024 * 1024) {
        throw const FormatException('Response exceeds limit.');
      }
      return Snapshot.fromJson(jsonDecode(text) as Map<String, dynamic>);
    } finally {
      client.close(force: true);
    }
  }
}

class GoreeCloudMonitorApp extends StatelessWidget {
  const GoreeCloudMonitorApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'GoreeCloud Monitor',
        debugShowCheckedModeBanner: false,
        themeMode: ThemeMode.system,
        theme: ThemeData(
            useMaterial3: true,
            colorScheme:
                ColorScheme.fromSeed(seedColor: const Color(0xFF5146C8))),
        darkTheme: ThemeData(
            useMaterial3: true,
            colorScheme: ColorScheme.fromSeed(
                seedColor: const Color(0xFFBFB8FF),
                brightness: Brightness.dark)),
        home: const MonitorHome(),
      );
}

class MonitorHome extends StatefulWidget {
  const MonitorHome({super.key});
  @override
  State<MonitorHome> createState() => _MonitorHomeState();
}

class _MonitorHomeState extends State<MonitorHome> with WidgetsBindingObserver {
  final address = TextEditingController();
  final client = StatusClient();
  Timer? timer;
  Snapshot? snapshot;
  String? error;
  bool working = false;
  bool foreground = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    timer = Timer.periodic(const Duration(minutes: 1), (_) {
      if (foreground) unawaited(refresh());
    });
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
  }

  Future<void> refresh() async {
    if (working || address.text.trim().isEmpty) return;
    setState(() {
      working = true;
      error = null;
    });
    try {
      final next = await client.read(address.text);
      if (mounted) setState(() => snapshot = next);
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e.toString();
          snapshot = null;
        });
      }
    } finally {
      if (mounted) setState(() => working = false);
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    address.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final services = snapshot?.services ?? [];
    final operational = services.where((s) => s.state == 'up').length;
    return Scaffold(
      appBar: AppBar(title: const Text('GoreeCloud Monitor'), actions: [
        IconButton(
            tooltip: 'Refresh status',
            onPressed: working ? null : refresh,
            icon: const Icon(Icons.refresh))
      ]),
      body: Center(
          child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: ListView(padding: const EdgeInsets.all(20), children: [
          Text('MONITORING OVERVIEW',
              style: theme.textTheme.labelLarge?.copyWith(
                  color: theme.colorScheme.primary, letterSpacing: 2)),
          const SizedBox(height: 12),
          Text('Know what is working.', style: theme.textTheme.headlineMedium),
          const SizedBox(height: 8),
          const Text(
              'Private, self-hosted monitoring. Only explicitly published status is shown.'),
          const SizedBox(height: 24),
          TextField(
              controller: address,
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.go,
              autocorrect: false,
              enableSuggestions: false,
              decoration: const InputDecoration(
                  labelText: 'HTTPS server address',
                  hintText: 'https://monitor.example.org',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.dns_outlined)),
              onSubmitted: (_) => refresh()),
          const SizedBox(height: 12),
          FilledButton.icon(
              onPressed: working ? null : refresh,
              icon: working
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.monitor_heart_outlined),
              label: Text(working ? 'Loading status…' : 'Connect')),
          if (error != null) ...[
            const SizedBox(height: 12),
            Semantics(
                liveRegion: true,
                child: Card(
                    color: theme.colorScheme.errorContainer,
                    child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(error!)))),
          ],
          const SizedBox(height: 26),
          if (snapshot == null)
            const Card(
                child: Padding(
                    padding: EdgeInsets.all(30),
                    child: Column(children: [
                      Icon(Icons.cloud_outlined, size: 44),
                      SizedBox(height: 12),
                      Text('No status loaded'),
                      SizedBox(height: 8),
                      Text('Enter a server URL to view published services.'),
                    ])))
          else ...[
            Card(
                child: ListTile(
                    title: const Text('Published services'),
                    subtitle: Text(
                        '${services.length} services · $operational operational'))),
            const SizedBox(height: 18),
            Text('Services', style: theme.textTheme.titleLarge),
            for (final item in services)
              Card(
                  child: ListTile(
                leading: Icon(
                    item.state == 'up'
                        ? Icons.check_circle_outline
                        : item.state == 'down'
                            ? Icons.error_outline
                            : Icons.schedule,
                    semanticLabel: 'Status ${item.state}',
                    color: item.state == 'up'
                        ? theme.colorScheme.primary
                        : theme.colorScheme.error),
                title: Text(item.name),
                subtitle: Text(item.state.toUpperCase()),
                trailing:
                    Text(item.latency == null ? '—' : '${item.latency} ms'),
              )),
            if (services.isEmpty) const Text('No monitors are published yet.'),
            const SizedBox(height: 20),
            Text('Active incidents', style: theme.textTheme.titleLarge),
            if (snapshot!.incidents.isEmpty)
              const Text('No currently published incidents.'),
            for (final name in snapshot!.incidents)
              Card(
                  child: ListTile(
                      leading: const Icon(Icons.warning_amber),
                      title: Text(name),
                      subtitle: const Text('Current outage'))),
          ],
          const SizedBox(height: 32),
          Text('GoreeCloud UI · GoreeShield privacy · Development preview',
              style: theme.textTheme.bodySmall),
        ]),
      )),
    );
  }
}
