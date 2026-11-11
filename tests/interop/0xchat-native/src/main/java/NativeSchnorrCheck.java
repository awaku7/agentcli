import fr.acinq.secp256k1.Secp256k1;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.List;

/**
 * Test UAG-generated NIP-01 Schnorr signatures with the same libsecp256k1
 * binding/API and version used by 0xChat's Android ChatcorePlugin.
 *
 * Test-only keys. This does not use any user's Nostr account or real DMs.
 */
public final class NativeSchnorrCheck {
    private NativeSchnorrCheck() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected vector path");
        List<String> vectors = Files.readAllLines(Path.of(args[0]));
        if (vectors.isEmpty()) throw new AssertionError("No vectors generated");

        Secp256k1 verifier = Secp256k1.get();
        HexFormat hex = HexFormat.of();
        int count = 0;
        for (String line : vectors) {
            if (line.isBlank()) continue;
            String[] columns = line.split("\\t", -1);
            if (columns.length != 5) throw new AssertionError("Invalid vector columns");
            boolean expected = columns[1].equals("valid");
            boolean actual = verifier.verifySchnorr(
                hex.parseHex(columns[2]),
                hex.parseHex(columns[3]),
                hex.parseHex(columns[4])
            );
            if (actual != expected) {
                throw new AssertionError("Schnorr verification mismatch: "
                    + columns[0] + " expected=" + expected + " actual=" + actual);
            }
            System.out.println("PASS " + columns[0] + " expected=" + expected);
            count++;
        }
        System.out.println("0xChat native verifier passed " + count + " UAG test vectors.");
    }
}
