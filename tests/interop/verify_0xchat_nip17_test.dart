// Integration test run against 0xChat's actual nostr_core_dart package.
// CI copies this file into the checked-out 0xChat package before flutter test.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:nostr_core_dart/nostr.dart';

void main() {
  test('UAG NIP-17 recipient and sender wraps decode in 0xChat', () async {
    final path = Platform.environment['UAG_NIP17_FIXTURE'];
    expect(path, isNotNull, reason: 'UAG_NIP17_FIXTURE must name the fixture');
    final fixture = jsonDecode(File(path!).readAsStringSync()) as Map<String, dynamic>;
    final cases = fixture['cases'] as List<dynamic>;
    expect(cases, isNotEmpty);

    for (final entry in cases) {
      final item = entry as Map<String, dynamic>;
      final recipientPublic = item['recipient_public_key'] as String;
      final recipientPrivate = item['recipient_private_key'] as String;
      final senderPublic = item['sender_public_key'] as String;
      final senderPrivate = item['sender_private_key'] as String;
      final expected = item['content'] as String;
      final label = item['name'] as String;

      final recipientWrap = await Event.fromJson(
        Map<String, dynamic>.from(item['recipient_wrap'] as Map),
        verify: false,
      );
      expect(recipientWrap.kind, 1059, reason: '$label outer kind');
      expect(await recipientWrap.isValid(), isTrue,
          reason: '$label outer Schnorr signature');
      expect(
        recipientWrap.tags.any((tag) =>
            tag.length >= 2 && tag[0] == 'p' && tag[1] == recipientPublic),
        isTrue,
        reason: '$label recipient p tag',
      );

      // Call the real 0xChat decryption/verification implementation, including
      // NIP-44 v2, kind-13 seal signature and kind-14 rumor extraction.
      final inner = await Nip17.decode(
        recipientWrap,
        recipientPublic,
        recipientPrivate,
      );
      expect(inner, isNotNull, reason: '$label decrypt recipient');
      expect(inner!.kind, 14, reason: '$label rumor kind');
      expect(inner.pubkey, senderPublic, reason: '$label authenticated sender');
      expect(inner.content, expected, reason: '$label plaintext');
      final dm = await Nip17.decodeSealedGossipDM(
        inner,
        recipientPublic,
        recipientPublic,
      );
      expect(dm, isNotNull, reason: '$label DM projection');
      expect(dm!.sender, senderPublic, reason: '$label DM sender');
      expect(dm.content, expected, reason: '$label rendered text');

      final senderWrap = await Event.fromJson(
        Map<String, dynamic>.from(item['sender_wrap'] as Map),
        verify: false,
      );
      expect(
        senderWrap.tags.any((tag) =>
            tag.length >= 2 && tag[0] == 'p' && tag[1] == senderPublic),
        isTrue,
        reason: '$label sender p tag',
      );
      final senderCopy = await Nip17.decode(
        senderWrap,
        senderPublic,
        senderPrivate,
      );
      expect(senderCopy, isNotNull, reason: '$label decrypt sender copy');
      expect(senderCopy!.id, inner.id, reason: '$label duplicate rumor identity');
    }
  });
}
