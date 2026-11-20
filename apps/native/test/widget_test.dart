import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:goreecloud_monitor/main.dart';

void main() {
  testWidgets('native monitor shows connection form', (tester) async {
    await tester.pumpWidget(const GoreeCloudMonitorApp());
    expect(find.text('GoreeCloud Monitor'), findsOneWidget);
    expect(find.text('No status loaded'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
    expect(find.text('Connect'), findsOneWidget);
  });

  test('published status decoder displays states and incident names', () {
    final data = Snapshot.fromJson({
      'monitors': [
        {'name': 'Home', 'state': 'up', 'last_latency_ms': 31}
      ],
      'incidents': [
        {'monitor_name': 'API'}
      ]
    });
    expect(data.services.single.name, 'Home');
    expect(data.services.single.latency, 31);
    expect(data.incidents.single, 'API');
  });
}
