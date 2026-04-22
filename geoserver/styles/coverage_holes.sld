<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd" version="1.1.0">
  <NamedLayer>
    <Name>coverage_holes</Name>
    <UserStyle>
      <Name>Coverage Holes Style</Name>
      <FeatureTypeStyle>
        <Rule>
          <Name>MR Data Hole (Square)</Name>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>data_source</ogc:PropertyName>
              <ogc:Literal>MR</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>square</WellKnownName>
                <Fill>
                  <CssParameter name="fill">
                    <ogc:Function name="Recode">
                      <ogc:Function name="mod">
                        <ogc:PropertyName>cluster_id</ogc:PropertyName>
                        <ogc:Literal>10</ogc:Literal>
                      </ogc:Function>
                      <ogc:Literal>0</ogc:Literal><ogc:Literal>#FF0000</ogc:Literal>
                      <ogc:Literal>1</ogc:Literal><ogc:Literal>#00FF00</ogc:Literal>
                      <ogc:Literal>2</ogc:Literal><ogc:Literal>#0000FF</ogc:Literal>
                      <ogc:Literal>3</ogc:Literal><ogc:Literal>#FFA500</ogc:Literal>
                      <ogc:Literal>4</ogc:Literal><ogc:Literal>#800080</ogc:Literal>
                      <ogc:Literal>5</ogc:Literal><ogc:Literal>#00FFFF</ogc:Literal>
                      <ogc:Literal>6</ogc:Literal><ogc:Literal>#FF00FF</ogc:Literal>
                      <ogc:Literal>7</ogc:Literal><ogc:Literal>#FFFF00</ogc:Literal>
                      <ogc:Literal>8</ogc:Literal><ogc:Literal>#A52A2A</ogc:Literal>
                      <ogc:Literal>9</ogc:Literal><ogc:Literal>#008080</ogc:Literal>
                    </ogc:Function>
                  </CssParameter>
                </Fill>
                <Stroke>
                  <CssParameter name="stroke">#FFFFFF</CssParameter>
                  <CssParameter name="stroke-width">1</CssParameter>
                </Stroke>
              </Mark>
              <Size>10</Size>
            </Graphic>
          </PointSymbolizer>
        </Rule>
        <Rule>
          <Name>Ookla Data Hole (Triangle)</Name>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>data_source</ogc:PropertyName>
              <ogc:Literal>Ookla</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>triangle</WellKnownName>
                <Fill>
                  <CssParameter name="fill">
                    <ogc:Function name="Recode">
                      <ogc:Function name="mod">
                        <ogc:PropertyName>cluster_id</ogc:PropertyName>
                        <ogc:Literal>10</ogc:Literal>
                      </ogc:Function>
                      <ogc:Literal>0</ogc:Literal><ogc:Literal>#FF0000</ogc:Literal>
                      <ogc:Literal>1</ogc:Literal><ogc:Literal>#00FF00</ogc:Literal>
                      <ogc:Literal>2</ogc:Literal><ogc:Literal>#0000FF</ogc:Literal>
                      <ogc:Literal>3</ogc:Literal><ogc:Literal>#FFA500</ogc:Literal>
                      <ogc:Literal>4</ogc:Literal><ogc:Literal>#800080</ogc:Literal>
                      <ogc:Literal>5</ogc:Literal><ogc:Literal>#00FFFF</ogc:Literal>
                      <ogc:Literal>6</ogc:Literal><ogc:Literal>#FF00FF</ogc:Literal>
                      <ogc:Literal>7</ogc:Literal><ogc:Literal>#FFFF00</ogc:Literal>
                      <ogc:Literal>8</ogc:Literal><ogc:Literal>#A52A2A</ogc:Literal>
                      <ogc:Literal>9</ogc:Literal><ogc:Literal>#008080</ogc:Literal>
                    </ogc:Function>
                  </CssParameter>
                </Fill>
                <Stroke>
                  <CssParameter name="stroke">#FFFFFF</CssParameter>
                  <CssParameter name="stroke-width">1</CssParameter>
                </Stroke>
              </Mark>
              <Size>12</Size>
            </Graphic>
          </PointSymbolizer>
        </Rule>
        <Rule>
          <Name>Noise Points</Name>
          <ogc:Filter>
            <ogc:PropertyIsEqualTo>
              <ogc:PropertyName>cluster_id</ogc:PropertyName>
              <ogc:Literal>-1</ogc:Literal>
            </ogc:PropertyIsEqualTo>
          </ogc:Filter>
          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>circle</WellKnownName>
                <Fill>
                  <CssParameter name="fill">#000000</CssParameter>
                </Fill>
                <Stroke>
                  <CssParameter name="stroke">#000000</CssParameter>
                  <CssParameter name="stroke-width">1</CssParameter>
                </Stroke>
              </Mark>
              <Size>3</Size>
            </Graphic>
          </PointSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
