package com.qualbench.bugs;

import java.util.ArrayList;
import java.util.List;

/**
 * Splits a single line of naive CSV into fields, respecting double-quoted
 * fields that may themselves contain commas.
 */
public class CsvFieldParser {

    /**
     * Splits {@code line} on commas, except commas that appear inside a
     * double-quoted field (e.g. {@code a,"b,c",d} -> ["a", "b,c", "d"]).
     * Surrounding quotes on a quoted field are stripped from the result.
     */
    public List<String> parseLine(String line) {
        List<String> fields = new ArrayList<>();
        // BUG: splits on every comma unconditionally, ignoring quoted
        // sections entirely -- a comma inside a quoted field incorrectly
        // starts a new field.
        for (String part : line.split(",")) {
            fields.add(part);
        }
        return fields;
    }
}
