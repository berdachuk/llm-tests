package com.qualbench.bugs;

import org.junit.jupiter.api.Test;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CsvFieldParserTest {

    private final CsvFieldParser parser = new CsvFieldParser();

    @Test
    void simpleUnquotedFields() {
        assertEquals(List.of("a", "b", "c"), parser.parseLine("a,b,c"));
    }

    @Test
    void quotedFieldContainingComma() {
        assertEquals(List.of("a", "b,c", "d"), parser.parseLine("a,\"b,c\",d"));
    }

    @Test
    void quotedFieldAtStart() {
        assertEquals(List.of("x,y", "z"), parser.parseLine("\"x,y\",z"));
    }

    @Test
    void emptyFieldsPreserved() {
        assertEquals(List.of("a", "", "c"), parser.parseLine("a,,c"));
    }

    @Test
    void allUnquotedNoCommaInside() {
        assertEquals(List.of("single"), parser.parseLine("single"));
    }
}
